import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  type Edge,
  type Node,
  type NodeProps,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import { getArcs, getGraph } from "@/api/client";
import type { ApiError } from "@/api/client";
import type { ArcsPage, Graph as GraphData } from "@/api/types";

/**
 * Grafo DAG — screen 6. Faithful to the Stitch mockup
 * (docs/design/stitch/grafo_dag_orc_hestrator/code.html): the DAG is rendered as
 * CARDS connected by arrowed edges — each node is a rounded-xl card showing the
 * short id, a status chip (icon + label), the title, and a footer strip. This
 * replaces the earlier Cytoscape "bubbles" render, which diverged from the
 * design.
 *
 * DATA — REAL, no fabrication. Two live endpoints:
 *   - GET /api/arcs -> { items: WorkItem[] }  (arc picker; default = first)
 *   - GET /api/graph/{arc_id} -> { nodes:[{data:{id,label,status,is_root}}],
 *                                  edges:[{data:{source,target}}] }
 *
 * RENDER — React Flow (@xyflow/react) with a custom node type (the card) and
 * dagre for automatic top-down hierarchical layout. Edges carry an arrow marker.
 */

// Status -> chip style (Tailwind token classes) + Material Symbol icon + label.
const STATUS_META: Record<
  string,
  { label: string; icon: string; chip: string; dot: string }
> = {
  queue: { label: "Fila", icon: "radio_button_unchecked", chip: "bg-status-queue/15 text-content-muted", dot: "#64788f" },
  work: { label: "Trabalhando", icon: "timelapse", chip: "bg-status-work/15 text-status-work", dot: "#ffc174" },
  review: { label: "Revisão", icon: "rate_review", chip: "bg-status-review/15 text-status-review", dot: "#a78bfa" },
  done: { label: "Feito", icon: "check_circle", chip: "bg-status-done/15 text-status-done", dot: "#4fd1c5" },
  blocked: { label: "Bloqueado", icon: "block", chip: "bg-status-blocked/15 text-status-blocked", dot: "#f87171" },
  cancelled: { label: "Cancelado", icon: "cancel", chip: "bg-surface-container-high text-content-muted", dot: "#52606d" },
  archived: { label: "Arquivado", icon: "inventory_2", chip: "bg-surface-container-high text-content-muted", dot: "#52606d" },
};

function statusMeta(status?: string) {
  return (status && STATUS_META[status]) || STATUS_META.queue;
}

const CARD_W = 208;
const CARD_H = 104;

// Node payload carried through React Flow.
type CardData = {
  label: string;
  status: string;
  isRoot: boolean;
  shortId: string;
};

/** The Stitch card: short id + status chip, title, footer strip. */
function TaskCardNode({ data }: NodeProps<Node<CardData>>) {
  const sm = statusMeta(data.status);
  return (
    <div
      className={`w-[208px] rounded-xl bg-surface-container p-space-sm shadow-lg transition-shadow hover:shadow-xl ${
        data.isRoot ? "ring-2 ring-primary" : "ring-1 ring-surface-variant/40"
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-surface-variant" />
      <div className="mb-1.5 flex items-center justify-between gap-1">
        <span className="font-label-sm text-label-sm font-bold text-on-surface-variant">
          #{data.shortId}
        </span>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-label-sm font-semibold ${sm.chip}`}
        >
          <span className="material-symbol text-[13px]">{sm.icon}</span>
          <span>{sm.label}</span>
        </span>
      </div>
      <p className="truncate font-display text-headline-sm font-semibold leading-tight text-on-surface" title={data.label}>
        {data.label}
      </p>
      <div className="mt-2 flex items-center justify-between rounded-lg bg-surface-container-low p-1.5 text-label-sm text-on-surface-variant">
        <span className="truncate">{data.isRoot ? "Raiz do arco" : "Tarefa"}</span>
        <span
          className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
          style={{ backgroundColor: sm.dot }}
          aria-hidden
        />
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-surface-variant" />
    </div>
  );
}

const nodeTypes = { taskCard: TaskCardNode };

/** Lay out nodes top-down with dagre; returns React Flow nodes + edges. */
function layout(graph: GraphData): { nodes: Node<CardData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 48, ranksep: 72, marginx: 24, marginy: 24 });

  for (const n of graph.nodes) {
    g.setNode(n.data.id, { width: CARD_W, height: CARD_H });
  }
  for (const e of graph.edges) {
    g.setEdge(e.data.source, e.data.target);
  }
  dagre.layout(g);

  const nodes: Node<CardData>[] = graph.nodes.map((n) => {
    const pos = g.node(n.data.id);
    return {
      id: n.data.id,
      type: "taskCard",
      position: { x: pos.x - CARD_W / 2, y: pos.y - CARD_H / 2 },
      data: {
        label: n.data.label,
        status: n.data.status ?? "queue",
        isRoot: Boolean(n.data.is_root),
        shortId: n.data.id.slice(0, 8),
      },
    };
  });

  const edges: Edge[] = graph.edges.map((e, i) => ({
    id: e.data.id ?? `${e.data.source}->${e.data.target}#${i}`,
    source: e.data.source,
    target: e.data.target,
    markerEnd: { type: MarkerType.ArrowClosed, color: "#4a6785" },
    style: { stroke: "#4a6785", strokeWidth: 1.5 },
  }));

  return { nodes, edges };
}

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

// --- React Flow canvas -----------------------------------------------------

function GraphCanvas({ graph }: { graph: GraphData }) {
  const { nodes, edges } = useMemo(() => layout(graph), [graph]);
  return (
    <div className="h-[34rem] w-full overflow-hidden rounded-2xl bg-surface-container-low/60 shadow-sm">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1c3c5a" gap={24} />
        <Controls showInteractive={false} className="!bg-surface-container !shadow-md" />
      </ReactFlow>
    </div>
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
            Hierarquia e dependências dos nós de um arco, como cards conectados. O nó raiz é destacado; as cores seguem o status.
          </p>
        </div>

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
                  style={{ backgroundColor: statusMeta(s).dot }}
                  aria-hidden
                />
                {statusMeta(s).label}
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
