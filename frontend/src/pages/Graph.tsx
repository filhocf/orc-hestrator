import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import cytoscape from "cytoscape";
import type { Core, ElementDefinition, Stylesheet } from "cytoscape";
import { getArcs, getGraph } from "@/api/client";
import type { ApiError } from "@/api/client";
import type { ArcsPage, Graph as GraphData } from "@/api/types";

/**
 * Grafo DAG — screen 6.
 *
 * The Stitch mockup referenced in the brief
 * (docs/design/stitch/grafo_dag_orc_hestrator/code.html) is NOT present on this
 * branch, so the layout follows the established design language of the already
 * ported screens (Overview / LiveTeam / Board / Arcs — tokens, Material
 * Symbols, loading/error/empty states) and renders the dependency/hierarchy DAG
 * of an arc's nodes.
 *
 * DATA — REAL, no fabrication. Two live endpoints:
 *   - GET /api/arcs -> { items: WorkItem[], ... }  (arc picker; default = first)
 *   - GET /api/graph/{arc_id} -> Cytoscape-native payload:
 *       { nodes: [{ data: { id, label, status, is_root } }],
 *         edges: [{ data: { source, target } }] }
 *   Shape confirmed live (http://127.0.0.1:8005/api/graph/<arc_id>): 9 nodes /
 *   8 edges for "ARC: Core Pipeline"; edges carry NO id (synthesized here).
 *
 * RENDER — Cytoscape.js (the API already speaks its element format). Layout is
 * the built-in `breadthfirst` (hierarchy top→down from the root node), chosen
 * over dagre to avoid a second runtime dependency. Nodes are coloured by status
 * using the EXACT theme status tokens; the root node (is_root) is enlarged and
 * ringed with the primary color.
 */

// Exact theme status tokens (tailwind.config.ts -> colors.status). Cytoscape
// styles need literal colors, so they are mirrored here (single source stays
// the theme; keep in sync if the palette changes).
const STATUS_COLOR: Record<string, string> = {
  queue: "#64788f",
  work: "#ffc174",
  review: "#a78bfa",
  done: "#4fd1c5",
  blocked: "#f87171",
  cancelled: "#52606d",
  archived: "#52606d",
};

const STATUS_LABEL: Record<string, string> = {
  queue: "Fila",
  work: "Trabalhando",
  review: "Revisão",
  done: "Concluído",
  blocked: "Bloqueado",
  cancelled: "Cancelado",
  archived: "Arquivado",
};

const PRIMARY = "#ffc174";
const SURFACE_CONTENT = "#e6eef6";
const EDGE_COLOR = "#1c3c5a";

function statusColor(status?: string): string {
  return (status && STATUS_COLOR[status]) || STATUS_COLOR.queue;
}

/** Build Cytoscape elements from the REAL graph payload (no invented data). */
function toElements(graph: GraphData): ElementDefinition[] {
  const nodes: ElementDefinition[] = graph.nodes.map((n) => ({
    data: {
      id: n.data.id,
      label: n.data.label,
      status: n.data.status ?? "queue",
      isRoot: Boolean(n.data.is_root),
    },
  }));
  const edges: ElementDefinition[] = graph.edges.map((e, i) => ({
    data: {
      id: e.data.id ?? `${e.data.source}->${e.data.target}#${i}`,
      source: e.data.source,
      target: e.data.target,
    },
  }));
  return [...nodes, ...edges];
}

const CY_STYLE: Stylesheet[] = [
  {
    selector: "node",
    style: {
      "background-color": "data(statusColor)" as unknown as string,
      label: "data(label)",
      color: SURFACE_CONTENT,
      "font-size": "11px",
      "font-family": "Inter, system-ui, sans-serif",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 6,
      "text-wrap": "wrap",
      "text-max-width": "120px",
      width: 34,
      height: 34,
      "border-width": 2,
      "border-color": "#0a2036",
    },
  },
  {
    // Root node (is_root) — larger, ringed with the primary accent.
    selector: "node[?isRoot]",
    style: {
      width: 52,
      height: 52,
      "border-width": 4,
      "border-color": PRIMARY,
      "font-size": "13px",
      "font-weight": "bold",
    },
  },
  {
    selector: "edge",
    style: {
      width: 2,
      "line-color": EDGE_COLOR,
      "target-arrow-color": EDGE_COLOR,
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      "arrow-scale": 1,
    },
  },
];

// --- Loading / error / empty primitives (aligned with Arcs/Board) ---------

function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container-low p-10 text-center shadow-sm">
      <span className="material-symbol text-[44px] text-status-blocked">error</span>
      <div className="flex flex-col gap-1">
        <h2 className="font-display text-headline-sm text-on-surface">Não foi possível carregar o grafo</h2>
        <p className="max-w-md text-body-sm text-on-surface-variant">
          {error.message ||
            "Ocorreu um erro ao falar com o Orc. Verifique se o serviço está no ar e tente novamente."}
        </p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="mt-1 flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-label-md font-semibold text-primary-contrast transition-opacity hover:opacity-90"
      >
        <span className="material-symbol text-[18px]">refresh</span>
        Tentar novamente
      </button>
    </div>
  );
}

function GraphSkeleton() {
  return (
    <div className="flex h-[32rem] w-full items-center justify-center rounded-2xl bg-surface-container-low">
      <span className="flex items-center gap-2 text-label-md text-on-surface-variant">
        <span className="material-symbol animate-spin text-[20px]">progress_activity</span>
        Carregando grafo…
      </span>
    </div>
  );
}

// --- Cytoscape canvas ------------------------------------------------------

/**
 * Mounts a Cytoscape instance into a div and re-renders when the graph data
 * changes. The instance is destroyed on unmount / data swap to avoid leaks.
 */
function GraphCanvas({ graph }: { graph: GraphData }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

  const elements = useMemo(() => toElements(graph), [graph]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const cy = cytoscape({
      container,
      elements,
      style: CY_STYLE,
      layout: {
        name: "breadthfirst",
        directed: true,
        spacingFactor: 1.3,
        padding: 24,
      },
      // Sensible interaction defaults; zoom-to-fit bounds set after layout.
      minZoom: 0.2,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
    });

    // Map status -> literal color on each node for the data(statusColor) style.
    cy.nodes().forEach((n) => {
      n.data("statusColor", statusColor(n.data("status")));
    });
    cy.fit(undefined, 32);
    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [elements]);

  return (
    <div
      ref={containerRef}
      data-testid="graph-canvas"
      className="h-[34rem] w-full rounded-2xl bg-surface-container-low/60 shadow-sm"
    />
  );
}

// --- Page ------------------------------------------------------------------

export default function Graph() {
  const [selectedArc, setSelectedArc] = useState<string | null>(null);

  const arcsQuery = useQuery<ArcsPage, ApiError>({
    queryKey: ["arcs"],
    queryFn: () => getArcs(),
  });

  const arcs = useMemo(() => arcsQuery.data?.items ?? [], [arcsQuery.data]);

  // Default to the first arc once the list loads (unless one is already chosen).
  useEffect(() => {
    if (!selectedArc && arcs.length > 0) {
      setSelectedArc(arcs[0].id);
    }
  }, [arcs, selectedArc]);

  const graphQuery = useQuery<GraphData, ApiError>({
    queryKey: ["graph", selectedArc],
    queryFn: () => getGraph(selectedArc as string),
    enabled: Boolean(selectedArc),
  });

  const graph = graphQuery.data;
  const nodeCount = graph?.nodes.length ?? 0;
  const edgeCount = graph?.edges.length ?? 0;

  // Status legend — only the statuses actually present in the current graph.
  const presentStatuses = useMemo(() => {
    if (!graph) return [] as string[];
    const seen = new Set<string>();
    for (const n of graph.nodes) seen.add(n.data.status ?? "queue");
    return [...seen];
  }, [graph]);

  return (
    <div className="flex w-full flex-col pb-10">
      {/* Header */}
      <div className="mb-6 flex flex-col justify-between gap-4 py-4 xl:flex-row xl:items-end">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <span className="material-symbol text-[18px]">hub</span>
            </span>
            <span className="text-label-sm font-bold uppercase tracking-widest text-primary">Dependências</span>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <h1 className="font-display text-headline-lg font-extrabold tracking-tight text-on-surface">
              Grafo DAG
            </h1>
            {graphQuery.isSuccess && (
              <span className="rounded-full bg-surface-container-high px-3 py-1 text-label-md text-on-surface-variant">
                {nodeCount} {nodeCount === 1 ? "nó" : "nós"} · {edgeCount}{" "}
                {edgeCount === 1 ? "aresta" : "arestas"}
              </span>
            )}
          </div>
          <p className="max-w-xl text-body-sm text-on-surface-variant">
            Hierarquia e dependências dos nós de um arco. O nó raiz é destacado; as cores seguem o status.
          </p>
        </div>

        {/* Arc selector (only when more than one arc exists) + updating hint */}
        <div className="flex items-center gap-3">
          {graphQuery.isFetching && !graphQuery.isLoading && (
            <span className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
              <span className="material-symbol animate-spin text-[16px]">progress_activity</span>
              Atualizando…
            </span>
          )}
          {arcs.length > 1 && (
            <label className="flex items-center gap-2 text-label-sm text-on-surface-variant">
              <span className="material-symbol text-[18px]">account_tree</span>
              <select
                aria-label="Selecionar arco"
                value={selectedArc ?? ""}
                onChange={(e) => setSelectedArc(e.target.value)}
                className="rounded-xl border border-surface-border bg-surface-container-high px-3 py-2 text-body-sm text-on-surface outline-none focus:border-primary"
              >
                {arcs.map((arc) => (
                  <option key={arc.id} value={arc.id}>
                    {arc.title}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </div>

      {/* Body */}
      {arcsQuery.isError ? (
        <ErrorState error={arcsQuery.error} onRetry={() => void arcsQuery.refetch()} />
      ) : graphQuery.isError ? (
        <ErrorState error={graphQuery.error} onRetry={() => void graphQuery.refetch()} />
      ) : arcsQuery.isLoading || graphQuery.isLoading || (!graph && Boolean(selectedArc)) ? (
        <GraphSkeleton />
      ) : arcs.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container-low p-16 text-center shadow-sm">
          <span className="material-symbol text-[48px] text-on-surface-variant">hub</span>
          <div className="flex flex-col gap-0.5">
            <p className="text-body-lg font-medium text-on-surface">Nenhum arco para exibir</p>
            <p className="max-w-sm text-body-sm text-on-surface-variant">
              Arcos (épicos com a tag "arc") e seus grafos aparecerão aqui assim que forem criados no Orc.
            </p>
          </div>
        </div>
      ) : graph && graph.nodes.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container-low p-16 text-center shadow-sm">
          <span className="material-symbol text-[48px] text-on-surface-variant">scatter_plot</span>
          <div className="flex flex-col gap-0.5">
            <p className="text-body-lg font-medium text-on-surface">Este arco não tem nós</p>
            <p className="max-w-sm text-body-sm text-on-surface-variant">
              Adicione tarefas ao arco para visualizar o grafo de dependências.
            </p>
          </div>
        </div>
      ) : graph ? (
        <div className="flex flex-col gap-4">
          <GraphCanvas graph={graph} />

          {/* Status legend — only statuses present in this graph */}
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-2xl bg-surface-container-low/60 px-4 py-3 shadow-sm">
            <span className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
              <span className="material-symbol text-[16px] text-primary">radio_button_checked</span>
              Nó raiz destacado
            </span>
            {presentStatuses.map((s) => (
              <span key={s} className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
                <span
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: statusColor(s) }}
                  aria-hidden
                />
                {STATUS_LABEL[s] ?? s}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <GraphSkeleton />
      )}
    </div>
  );
}
