import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getArcChildren, getArcs } from "@/api/client";
import type { ApiError } from "@/api/client";
import type { ArcChildren, ArcsPage, ItemStatus, Priority, WorkItem } from "@/api/types";

/**
 * Árvore de Arcos — screen 5.
 *
 * The Stitch mockup referenced in the brief
 * (docs/design/stitch/rvore_de_arcos_orc_hestrator/code.html) is NOT present on
 * this branch, so the layout follows the established design language of the
 * already-ported screens (Overview.tsx / LiveTeam.tsx / Board.tsx — tokens,
 * Material Symbols, loading/error/empty states, status/priority badges).
 *
 * TREE STRATEGY — lazy load on expand:
 *   - Root arcs come from GET /api/arcs -> { items: WorkItem[], ... }
 *     (items = root arcs: parent_id null, tags include "arc").
 *   - Expanding a node fetches its direct children via
 *     GET /api/arcs/{id} -> { children: WorkItem[] }.
 *   - Each child can itself be expanded (recursive), fetched on demand. This
 *     keeps the initial payload tiny and matches the collapse/expand UX of a
 *     hierarchy tree. React-query caches each node's children by id, so
 *     re-expanding is instant.
 *
 * HONESTY CONTRACT — only REAL fields are rendered. No `progress %` field
 * exists on a WorkItem, so the only progress shown is DERIVED from the direct
 * children that are already loaded (done / total), and it is labelled as such
 * ("N/M concluídos"). It is only shown once a node's children are loaded.
 * created_by is NULL for every seeded item, so responsável shows an explicit
 * "sem responsável" rather than inventing an assignee.
 */

// --- Status + priority metadata (aligned with Board.tsx) ------------------

const STATUS_META: Record<ItemStatus, { label: string; dot: string; chip: string }> = {
  queue: { label: "Fila", dot: "bg-status-queue", chip: "bg-status-queue/20 text-content-muted" },
  work: { label: "Trabalhando", dot: "bg-status-work", chip: "bg-status-work/15 text-status-work" },
  review: { label: "Revisão", dot: "bg-status-review", chip: "bg-status-review/15 text-status-review" },
  done: { label: "Concluído", dot: "bg-status-done", chip: "bg-status-done/15 text-status-done" },
  blocked: { label: "Bloqueado", dot: "bg-status-blocked", chip: "bg-status-blocked/15 text-status-blocked" },
  cancelled: { label: "Cancelado", dot: "bg-status-cancelled", chip: "bg-status-cancelled/15 text-content-muted" },
  archived: { label: "Arquivado", dot: "bg-surface-variant", chip: "bg-surface-container-high text-content-muted" },
};

const PRIORITY_META: Record<Priority, { label: string; chip: string }> = {
  critical: { label: "Crítica", chip: "bg-status-blocked/15 text-status-blocked" },
  high: { label: "Alta", chip: "bg-primary/15 text-primary" },
  medium: { label: "Média", chip: "bg-status-review/15 text-status-review" },
  low: { label: "Baixa", chip: "bg-status-queue/20 text-content-muted" },
};

function statusMeta(s: ItemStatus) {
  return STATUS_META[s] ?? STATUS_META.queue;
}
function priorityMeta(p: Priority) {
  return PRIORITY_META[p] ?? PRIORITY_META.medium;
}

/** Parse the "tags" CSV field into a clean array. */
function parseTags(tags: string | null | undefined): string[] {
  if (!tags) return [];
  return tags.split(",").map((t) => t.trim()).filter(Boolean);
}

/** An item is an arc (epic) when it carries the "arc" tag or item_type "arc". */
function isArc(item: WorkItem): boolean {
  return item.item_type === "arc" || parseTags(item.tags).includes("arc");
}

// --- Loading / error / empty primitives -----------------------------------

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-container-high/60 ${className}`} />;
}

function TreeSkeleton() {
  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-surface-container-low p-4">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-14 w-full" />
      ))}
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container-low p-10 text-center shadow-sm">
      <span className="material-symbol text-[44px] text-status-blocked">error</span>
      <div className="flex flex-col gap-1">
        <h2 className="font-display text-headline-sm text-on-surface">Não foi possível carregar os arcos</h2>
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

// --- Node ------------------------------------------------------------------

interface NodeProps {
  item: WorkItem;
  depth: number;
}

/**
 * A single tree node. Children are fetched lazily the first time the node is
 * expanded, and cached by react-query (queryKey ["arc-children", id]).
 */
function TreeNode({ item, depth }: NodeProps) {
  const [expanded, setExpanded] = useState(false);
  const arc = isArc(item);
  const sm = statusMeta(item.status);
  const pm = priorityMeta(item.priority);
  const tags = parseTags(item.tags).filter((t) => t !== "arc");
  const assignee = item.updated_by ?? item.created_by; // REAL fields; null in current seed

  const childrenQuery = useQuery<ArcChildren, ApiError>({
    queryKey: ["arc-children", item.id],
    queryFn: () => getArcChildren(item.id),
    enabled: expanded,
    staleTime: 30_000,
  });

  const children = childrenQuery.data?.children ?? [];
  const loaded = childrenQuery.isSuccess;
  const hasKnownChildren = loaded && children.length > 0;
  // Derived progress — only meaningful once children are loaded. Counts the
  // DIRECT children that are "done". Explicitly labelled as derived.
  const doneCount = children.filter((c) => c.status === "done").length;

  // We don't know if a node has children until we fetch. The chevron is always
  // offered (except when we've loaded and found none), and expanding reveals
  // the loading/empty state inline.
  const canExpand = !loaded || hasKnownChildren;

  return (
    <div className="flex flex-col">
      {/* Row */}
      <div
        className="group flex items-center gap-2 rounded-xl px-3 py-2.5 transition-colors hover:bg-surface-container-low"
        style={{ marginLeft: depth * 20 }}
      >
        {/* Expand/collapse toggle */}
        {canExpand ? (
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={expanded ? "Recolher" : "Expandir"}
            onClick={() => setExpanded((v) => !v)}
            className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md text-on-surface-variant transition-colors hover:bg-surface-container-high"
          >
            <span className="material-symbol text-[20px]">
              {expanded ? "expand_more" : "chevron_right"}
            </span>
          </button>
        ) : (
          <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center text-on-surface-variant/40">
            <span className="material-symbol text-[18px]">remove</span>
          </span>
        )}

        {/* Node icon: arcs are trees, leaves are tasks */}
        <span
          className={`material-symbol flex-shrink-0 text-[20px] ${arc ? "text-primary" : "text-on-surface-variant"}`}
        >
          {arc ? "account_tree" : "task_alt"}
        </span>

        {/* Title — links to the task detail page */}
        <Link
          to={`/task/${item.id}`}
          className={`min-w-0 flex-1 truncate transition-colors hover:text-primary hover:underline ${
            arc ? "font-display text-label-lg font-bold text-on-surface" : "text-body-md text-on-surface"
          }`}
          title={item.title}
        >
          {item.title}
        </Link>

        {/* Derived progress (done/total of loaded direct children) */}
        {hasKnownChildren ? (
          <span
            className="hidden items-center gap-1 rounded-full bg-surface-container-high px-2 py-0.5 text-label-sm text-on-surface-variant sm:flex"
            title="Concluídos entre os filhos diretos já carregados"
          >
            <span className="material-symbol text-[14px]">donut_small</span>
            {doneCount}/{children.length} concluídos
          </span>
        ) : null}

        {/* Priority badge */}
        <span className={`hidden rounded px-1.5 py-0.5 text-label-sm font-bold md:inline ${pm.chip}`}>
          {pm.label}
        </span>

        {/* Status badge */}
        <span className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-label-sm font-semibold ${sm.chip}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${sm.dot}`} />
          {sm.label}
        </span>

        {/* Tags (non-arc) */}
        {tags.map((t) => (
          <span
            key={t}
            className="hidden rounded bg-surface-container-high px-1.5 py-0.5 text-label-sm text-on-surface-variant lg:inline"
          >
            #{t}
          </span>
        ))}

        {/* Responsável — REAL created_by/updated_by (null in seed) */}
        <span
          className="hidden items-center gap-1 text-label-sm text-on-surface-variant xl:flex"
          title="Responsável (created_by / updated_by)"
        >
          <span className="material-symbol text-[14px]">{assignee ? "person" : "person_off"}</span>
          <span className="max-w-[9rem] truncate">{assignee ?? "sem responsável"}</span>
        </span>
      </div>

      {/* Children */}
      {expanded ? (
        <div className="flex flex-col border-l border-surface-variant/40" style={{ marginLeft: depth * 20 + 11 }}>
          {childrenQuery.isLoading ? (
            <div className="flex items-center gap-2 px-4 py-2 text-label-sm text-on-surface-variant">
              <span className="material-symbol animate-spin text-[16px]">progress_activity</span>
              Carregando filhos…
            </div>
          ) : childrenQuery.isError ? (
            <div className="flex items-center gap-2 px-4 py-2 text-label-sm text-status-blocked">
              <span className="material-symbol text-[16px]">error</span>
              Erro ao carregar filhos
              <button
                type="button"
                onClick={() => void childrenQuery.refetch()}
                className="ml-1 rounded-md bg-surface-container-high px-2 py-0.5 font-semibold text-on-surface hover:bg-surface-container-highest"
              >
                Tentar novamente
              </button>
            </div>
          ) : children.length === 0 ? (
            <div className="px-4 py-2 text-label-sm text-on-surface-variant">Nenhum item neste nó.</div>
          ) : (
            children.map((child) => <TreeNode key={child.id} item={child} depth={depth + 1} />)
          )}
        </div>
      ) : null}
    </div>
  );
}

// --- Page ------------------------------------------------------------------

export default function Arcs() {
  const arcsQuery = useQuery<ArcsPage, ApiError>({
    queryKey: ["arcs"],
    queryFn: () => getArcs(),
  });

  const arcs = arcsQuery.data?.items ?? [];
  const total = arcsQuery.data?.total ?? 0;

  return (
    <div className="flex w-full flex-col pb-10">
      {/* Header */}
      <div className="mb-6 flex flex-col justify-between gap-4 py-4 xl:flex-row xl:items-end">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <span className="material-symbol text-[18px]">account_tree</span>
            </span>
            <span className="text-label-sm font-bold uppercase tracking-widest text-primary">Hierarquia</span>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <h1 className="font-display text-headline-lg font-extrabold tracking-tight text-on-surface">
              Árvore de Arcos
            </h1>
            {!arcsQuery.isLoading && !arcsQuery.isError && (
              <span className="rounded-full bg-surface-container-high px-3 py-1 text-label-md text-on-surface-variant">
                {total} {total === 1 ? "arco" : "arcos"}
              </span>
            )}
          </div>
          <p className="max-w-xl text-body-sm text-on-surface-variant">
            Épicos (arcos) e suas tarefas. Clique para expandir um nó — os filhos são carregados sob demanda.
          </p>
        </div>
        {arcsQuery.isFetching && !arcsQuery.isLoading && (
          <span className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
            <span className="material-symbol animate-spin text-[16px]">progress_activity</span>
            Atualizando…
          </span>
        )}
      </div>

      {/* Body */}
      {arcsQuery.isError ? (
        <ErrorState error={arcsQuery.error} onRetry={() => void arcsQuery.refetch()} />
      ) : arcsQuery.isLoading ? (
        <TreeSkeleton />
      ) : arcs.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container-low p-16 text-center shadow-sm">
          <span className="material-symbol text-[48px] text-on-surface-variant">account_tree</span>
          <div className="flex flex-col gap-0.5">
            <p className="text-body-lg font-medium text-on-surface">Nenhum arco cadastrado</p>
            <p className="max-w-sm text-body-sm text-on-surface-variant">
              Arcos (épicos com a tag "arc") aparecerão aqui assim que forem criados no Orc.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-1 rounded-2xl bg-surface-container-low/60 p-3 shadow-sm">
          {arcs.map((arc) => (
            <TreeNode key={arc.id} item={arc} depth={0} />
          ))}
        </div>
      )}
    </div>
  );
}
