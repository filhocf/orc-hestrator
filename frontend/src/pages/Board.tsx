import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { advanceItem, getItemsPage } from "@/api/client";
import type { ApiError } from "@/api/client";
import type { AdvanceTrigger, ItemsPage, ItemStatus, Priority, WorkItem } from "@/api/types";

/**
 * Board (Kanban) — screen 4.
 *
 * The Stitch mockup referenced in the brief
 * (docs/design/stitch/board_kanban_orc_hestrator/code.html) is NOT present on
 * this branch, so the layout follows (a) the established design language of the
 * already-ported screens (Overview.tsx / LiveTeam.tsx — tokens, Material
 * Symbols, loading/error/empty states) and (b) the structure of the legacy
 * server-rendered board (src/task_orchestrator/ui/templates/board.html):
 *   - columns per status (queue=Fila, work=Trabalhando, review=Revisão,
 *     done=Concluído; blocked/cancelled become extra columns when non-empty)
 *   - swimlanes grouped by parent arc
 *   - priority indicator + tags on each card
 *
 * HONESTY CONTRACT — only REAL fields from GET /api/items are rendered. Shape
 * confirmed live (http://127.0.0.1:8005/api/items):
 *   { items: WorkItem[], total, limit, offset }, each item:
 *   { id, parent_id, title, description, summary, status, priority, tags (CSV),
 *     item_type, complexity, created_by, updated_by, created_at, ... }
 *
 * The mockup's typical "agente responsável" avatar is backed by created_by /
 * updated_by — which are NULL for every seeded item right now, so the card
 * shows an explicit "sem responsável" instead of inventing an assignee.
 * description/summary/complexity are also empty in the seed and are only shown
 * when actually present.
 */

// --- Column + priority metadata -------------------------------------------

interface ColumnMeta {
  status: ItemStatus;
  label: string;
  icon: string;
  dot: string; // bg token for the header dot
  accent: string; // left-accent on cards
  text: string; // header text token
}

/** The four primary flow columns, in board order. */
const PRIMARY_COLUMNS: ColumnMeta[] = [
  { status: "queue", label: "Fila", icon: "inbox", dot: "bg-status-queue", accent: "bg-status-queue", text: "text-status-queue" },
  { status: "work", label: "Trabalhando", icon: "bolt", dot: "bg-status-work", accent: "bg-status-work", text: "text-status-work" },
  { status: "review", label: "Revisão", icon: "rate_review", dot: "bg-status-review", accent: "bg-status-review", text: "text-status-review" },
  { status: "done", label: "Concluído", icon: "check_circle", dot: "bg-status-done", accent: "bg-status-done", text: "text-status-done" },
];

/** Extra columns rendered only when they actually contain items. */
const EXTRA_COLUMNS: ColumnMeta[] = [
  { status: "blocked", label: "Bloqueado", icon: "block", dot: "bg-status-blocked", accent: "bg-status-blocked", text: "text-status-blocked" },
  { status: "cancelled", label: "Cancelado", icon: "cancel", dot: "bg-status-cancelled", accent: "bg-status-cancelled", text: "text-status-cancelled" },
];

const PRIORITY_META: Record<Priority, { label: string; dot: string; chip: string }> = {
  critical: { label: "Crítica", dot: "bg-status-blocked", chip: "bg-status-blocked/15 text-status-blocked" },
  high: { label: "Alta", dot: "bg-primary", chip: "bg-primary/15 text-primary" },
  medium: { label: "Média", dot: "bg-status-review", chip: "bg-status-review/15 text-status-review" },
  low: { label: "Baixa", dot: "bg-status-queue", chip: "bg-status-queue/20 text-content-muted" },
};

/** advance() trigger offered on a card, by current status. */
const NEXT_TRIGGER: Partial<Record<ItemStatus, { trigger: AdvanceTrigger; label: string; icon: string }>> = {
  queue: { trigger: "start", label: "Iniciar", icon: "play_arrow" },
  work: { trigger: "complete", label: "Concluir", icon: "task_alt" },
  review: { trigger: "complete", label: "Aprovar", icon: "done_all" },
  blocked: { trigger: "reopen", label: "Reabrir", icon: "restart_alt" },
};

// --- Helpers ---------------------------------------------------------------

/** Parse the "tags" CSV field into a clean array. */
function parseTags(tags: string | null | undefined): string[] {
  if (!tags) return [];
  return tags.split(",").map((t) => t.trim()).filter(Boolean);
}

function priorityMeta(p: Priority): { label: string; dot: string; chip: string } {
  return PRIORITY_META[p] ?? PRIORITY_META.medium;
}

interface Swimlane {
  key: string;
  title: string;
  isArc: boolean;
  items: WorkItem[];
}

/**
 * Group items into swimlanes by parent arc. An item whose parent_id matches a
 * known item's id is placed under that parent's lane (resolving the real arc
 * title); items without a resolvable parent go to a single "Sem arco" lane.
 * Arc items themselves (tags include "arc" / item_type === "arc") are used only
 * as lane headers, not rendered as cards.
 */
function buildSwimlanes(items: WorkItem[]): Swimlane[] {
  const byId = new Map(items.map((i) => [i.id, i]));
  const isArc = (i: WorkItem) => i.item_type === "arc" || parseTags(i.tags).includes("arc");

  const lanes = new Map<string, Swimlane>();
  const OTHER = "__other__";

  for (const item of items) {
    if (isArc(item)) continue; // arcs are headers, not cards
    const parent = item.parent_id ? byId.get(item.parent_id) : undefined;
    const key = parent ? parent.id : OTHER;
    const title = parent ? parent.title : "Sem arco";
    const lane = lanes.get(key) ?? { key, title, isArc: Boolean(parent), items: [] };
    lane.items.push(item);
    lanes.set(key, lane);
  }

  // Stable order: named arcs first (alpha), "Sem arco" last.
  return [...lanes.values()].sort((a, b) => {
    if (a.key === OTHER) return 1;
    if (b.key === OTHER) return -1;
    return a.title.localeCompare(b.title);
  });
}

// --- Loading / error / empty primitives -----------------------------------

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-container-high/60 ${className}`} />;
}

function BoardSkeleton({ columns }: { columns: ColumnMeta[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {columns.map((c) => (
        <div key={c.status} className="flex flex-col gap-3 rounded-2xl bg-surface-container-low p-3">
          <Skeleton className="h-6 w-28" />
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ))}
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container-low p-10 text-center shadow-sm">
      <span className="material-symbol text-[44px] text-status-blocked">error</span>
      <div className="flex flex-col gap-1">
        <h2 className="font-display text-headline-sm text-on-surface">Não foi possível carregar o board</h2>
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

function ColumnEmpty() {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed border-surface-variant/60 px-3 py-6 text-center">
      <span className="material-symbol text-[22px] text-on-surface-variant">check_indeterminate_small</span>
      <span className="text-label-sm text-on-surface-variant">Nenhum item</span>
    </div>
  );
}

// --- Card ------------------------------------------------------------------

function TaskCard({
  item,
  accent,
  onAdvance,
  advancing,
}: {
  item: WorkItem;
  accent: string;
  onAdvance: (item: WorkItem, trigger: AdvanceTrigger) => void;
  advancing: boolean;
}) {
  const pm = priorityMeta(item.priority);
  const tags = parseTags(item.tags);
  const assignee = item.updated_by ?? item.created_by; // REAL fields; null in current seed
  const next = NEXT_TRIGGER[item.status];

  return (
    <div className="group relative flex flex-col gap-2.5 overflow-hidden rounded-xl bg-surface-container-low p-3 shadow-sm transition-colors hover:bg-surface-container">
      <div className={`absolute bottom-0 left-0 top-0 w-1 ${accent}`} />

      {/* Priority + title */}
      <div className="flex items-start gap-2 pl-1.5">
        <span className={`mt-1 h-2 w-2 flex-shrink-0 rounded-full ${pm.dot}`} title={`Prioridade: ${pm.label}`} />
        <Link
          to={`/task/${item.id}`}
          className="text-label-lg font-semibold leading-snug text-on-surface transition-colors hover:text-primary hover:underline"
          title="Abrir detalhe da tarefa"
        >
          {item.title}
        </Link>
      </div>

      {/* Optional description — only when the API actually has one */}
      {item.description ? (
        <p className="line-clamp-2 pl-3.5 text-body-sm text-on-surface-variant">{item.description}</p>
      ) : null}

      {/* Priority chip + tags */}
      <div className="flex flex-wrap items-center gap-1.5 pl-3.5">
        <span className={`rounded px-1.5 py-0.5 text-label-sm font-bold ${pm.chip}`}>{pm.label}</span>
        {tags.map((t) => (
          <span
            key={t}
            className="rounded bg-surface-container-high px-1.5 py-0.5 text-label-sm text-on-surface-variant"
          >
            #{t}
          </span>
        ))}
      </div>

      {/* Footer: responsável (real created_by/updated_by) + advance */}
      <div className="mt-0.5 flex items-center justify-between gap-2 pl-3.5">
        <span className="flex items-center gap-1 text-label-sm text-on-surface-variant" title="Responsável (created_by / updated_by)">
          <span className="material-symbol text-[14px]">{assignee ? "person" : "person_off"}</span>
          <span className="max-w-[9rem] truncate">{assignee ?? "sem responsável"}</span>
        </span>
        {next ? (
          <button
            type="button"
            disabled={advancing}
            onClick={() => onAdvance(item, next.trigger)}
            className="flex items-center gap-1 rounded-lg bg-surface-container-high px-2 py-1 text-label-sm font-semibold text-on-surface opacity-0 transition-all hover:bg-surface-container-highest focus:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-40"
            title={`${next.label} esta tarefa`}
          >
            <span className="material-symbol text-[14px]">{advancing ? "progress_activity" : next.icon}</span>
            {next.label}
          </button>
        ) : null}
      </div>
    </div>
  );
}

// --- Column ----------------------------------------------------------------

function Column({
  meta,
  items,
  onAdvance,
  advancingId,
}: {
  meta: ColumnMeta;
  items: WorkItem[];
  onAdvance: (item: WorkItem, trigger: AdvanceTrigger) => void;
  advancingId: string | null;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-3 rounded-2xl bg-surface-container-low/60 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${meta.dot}`} />
          <span className="material-symbol text-[18px] text-on-surface-variant">{meta.icon}</span>
          <h2 className={`text-label-lg font-bold uppercase tracking-tight ${meta.text}`}>{meta.label}</h2>
        </div>
        <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-sm font-bold text-on-surface-variant">
          {items.length}
        </span>
      </div>
      <div className="flex flex-col gap-2.5">
        {items.length === 0 ? (
          <ColumnEmpty />
        ) : (
          items.map((item) => (
            <TaskCard
              key={item.id}
              item={item}
              accent={meta.accent}
              onAdvance={onAdvance}
              advancing={advancingId === item.id}
            />
          ))
        )}
      </div>
    </div>
  );
}

// --- Page ------------------------------------------------------------------

export default function Board() {
  const queryClient = useQueryClient();
  const [advancingId, setAdvancingId] = useState<string | null>(null);

  const itemsQuery = useQuery<ItemsPage, ApiError>({
    queryKey: ["items", "board"],
    // Fetch a generous page; the seed is small and the board shows everything.
    queryFn: () => getItemsPage({ limit: 200 }),
  });

  const advanceMutation = useMutation<WorkItem, ApiError, { id: string; trigger: AdvanceTrigger }>({
    mutationFn: ({ id, trigger }) => advanceItem(id, trigger),
    onMutate: ({ id }) => setAdvancingId(id),
    onSettled: () => {
      setAdvancingId(null);
      void queryClient.invalidateQueries({ queryKey: ["items", "board"] });
    },
  });

  const items = useMemo(() => itemsQuery.data?.items ?? [], [itemsQuery.data]);

  // Decide which columns to show: the four primary flow states always, plus any
  // extra state (blocked/cancelled) that actually has items.
  const columns = useMemo<ColumnMeta[]>(() => {
    const extras = EXTRA_COLUMNS.filter((c) => items.some((i) => i.status === c.status));
    return [...PRIMARY_COLUMNS, ...extras];
  }, [items]);

  const lanes = useMemo(() => buildSwimlanes(items), [items]);

  const handleAdvance = (item: WorkItem, trigger: AdvanceTrigger) =>
    advanceMutation.mutate({ id: item.id, trigger });

  const total = itemsQuery.data?.total ?? 0;

  return (
    <div className="flex w-full flex-col pb-10">
      {/* Header */}
      <div className="mb-6 flex flex-col justify-between gap-4 py-4 xl:flex-row xl:items-end">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <span className="material-symbol text-[18px]">view_kanban</span>
            </span>
            <span className="text-label-sm font-bold uppercase tracking-widest text-primary">
              Fluxo de trabalho
            </span>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <h1 className="font-display text-headline-lg font-extrabold tracking-tight text-on-surface">Board</h1>
            {!itemsQuery.isLoading && !itemsQuery.isError && (
              <span className="rounded-full bg-surface-container-high px-3 py-1 text-label-md text-on-surface-variant">
                {total} {total === 1 ? "tarefa" : "tarefas"} em {lanes.length}{" "}
                {lanes.length === 1 ? "arco" : "arcos"}
              </span>
            )}
          </div>
        </div>
        {itemsQuery.isFetching && !itemsQuery.isLoading && (
          <span className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
            <span className="material-symbol animate-spin text-[16px]">progress_activity</span>
            Atualizando…
          </span>
        )}
      </div>

      {/* Body */}
      {itemsQuery.isError ? (
        <ErrorState error={itemsQuery.error} onRetry={() => void itemsQuery.refetch()} />
      ) : itemsQuery.isLoading ? (
        <BoardSkeleton columns={PRIMARY_COLUMNS} />
      ) : lanes.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container-low p-16 text-center shadow-sm">
          <span className="material-symbol text-[48px] text-on-surface-variant">inbox</span>
          <div className="flex flex-col gap-0.5">
            <p className="text-body-lg font-medium text-on-surface">Nenhuma tarefa no board</p>
            <p className="max-w-sm text-body-sm text-on-surface-variant">
              Itens de trabalho aparecerão aqui assim que forem criados no Orc.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {lanes.map((lane) => (
            <section key={lane.key} className="flex flex-col gap-3">
              {/* Swimlane header */}
              <div className="flex items-center gap-2 rounded-xl bg-surface-container px-4 py-2.5 shadow-sm">
                <span className="material-symbol text-[20px] text-primary">
                  {lane.isArc ? "account_tree" : "folder_open"}
                </span>
                <h2 className="font-display text-label-lg font-bold tracking-tight text-on-surface">{lane.title}</h2>
                <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-sm font-bold text-on-surface-variant">
                  {lane.items.length}
                </span>
              </div>

              {/* Columns for this lane */}
              <div
                className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
                style={columns.length > 4 ? { gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))` } : undefined}
              >
                {columns.map((meta) => (
                  <Column
                    key={meta.status}
                    meta={meta}
                    items={lane.items.filter((i) => i.status === meta.status)}
                    onAdvance={handleAdvance}
                    advancingId={advancingId}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
