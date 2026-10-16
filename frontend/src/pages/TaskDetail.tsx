import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { advanceItem, getItemDetail } from "@/api/client";
import type { ApiError } from "@/api/client";
import type {
  AdvanceTrigger,
  ClaimOwner,
  DependencyEdge,
  ItemDetail,
  ItemNote,
  ItemStatus,
  Priority,
  WorkItem,
} from "@/api/types";

/**
 * Detalhe da tarefa — screen 7 (/task/:id).
 *
 * The Stitch mockup referenced in the brief
 * (docs/design/stitch/detalhe_da_tarefa_orc_hestrator/code.html) is NOT present
 * on this branch, so the layout follows (a) the established design language of
 * the already-ported screens (Overview/LiveTeam/Board/Arcs/Graph — tokens,
 * Material Symbols, loading/error/empty states, status/priority badges) and
 * (b) the structure of the legacy server-rendered detail partial
 * (src/task_orchestrator/ui/templates/partials/item_detail.html): priority +
 * title, status/tags, description, id/created, and the list of children.
 *
 * DATA — full detail via react-query (queryKey ["item", id]) from the REAL
 * endpoint GET /api/items/{id}. Shape confirmed live
 * (http://127.0.0.1:8005/api/items/<id>): a flattened WorkItem plus
 *   children:     WorkItem[]
 *   notes:        ItemNote[]          (notes table rows)
 *   dependencies: { blocks: DependencyEdge[], blocked_by: DependencyEdge[] }
 *   claim:        ClaimOwner | null   (active claim owner triple)
 *
 * HONESTY CONTRACT — only REAL fields are rendered. created_by / updated_by are
 * NULL for every seeded item, so authorship shows an explicit "sem responsável"
 * instead of inventing a name. notes / dependencies / children are empty in the
 * current seed, so each section renders its own empty state. description /
 * summary / due_at / previous_status / complexity are only shown when present.
 */

// --- Status + priority metadata (aligned with Board.tsx / Arcs.tsx) --------

const STATUS_META: Record<ItemStatus, { label: string; dot: string; chip: string }> = {
  queue: { label: "Fila", dot: "bg-status-queue", chip: "bg-status-queue/20 text-content-muted" },
  work: { label: "Trabalhando", dot: "bg-status-work", chip: "bg-status-work/15 text-status-work" },
  review: { label: "Revisão", dot: "bg-status-review", chip: "bg-status-review/15 text-status-review" },
  done: { label: "Concluído", dot: "bg-status-done", chip: "bg-status-done/15 text-status-done" },
  blocked: { label: "Bloqueado", dot: "bg-status-blocked", chip: "bg-status-blocked/15 text-status-blocked" },
  cancelled: { label: "Cancelado", dot: "bg-status-cancelled", chip: "bg-status-cancelled/15 text-content-muted" },
  archived: { label: "Arquivado", dot: "bg-surface-variant", chip: "bg-surface-container-high text-content-muted" },
};

const PRIORITY_META: Record<Priority, { label: string; dot: string; chip: string }> = {
  critical: { label: "Crítica", dot: "bg-status-blocked", chip: "bg-status-blocked/15 text-status-blocked" },
  high: { label: "Alta", dot: "bg-primary", chip: "bg-primary/15 text-primary" },
  medium: { label: "Média", dot: "bg-status-review", chip: "bg-status-review/15 text-status-review" },
  low: { label: "Baixa", dot: "bg-status-queue", chip: "bg-status-queue/20 text-content-muted" },
};

function statusMeta(s: ItemStatus | string): { label: string; dot: string; chip: string } {
  return STATUS_META[s as ItemStatus] ?? STATUS_META.queue;
}
function priorityMeta(p: Priority): { label: string; dot: string; chip: string } {
  return PRIORITY_META[p] ?? PRIORITY_META.medium;
}

/**
 * advance() actions offered for the current status, mirroring the engine
 * transitions (engine/base.py TRANSITIONS). Each status exposes the triggers
 * that are actually valid from it; the backend is the source of truth and will
 * reject anything else with a structured error we surface inline.
 */
const ADVANCE_ACTIONS: Partial<
  Record<ItemStatus, { trigger: AdvanceTrigger; label: string; icon: string; tone: "primary" | "neutral" | "danger" }[]>
> = {
  queue: [
    { trigger: "start", label: "Iniciar", icon: "play_arrow", tone: "primary" },
    { trigger: "block", label: "Bloquear", icon: "block", tone: "danger" },
    { trigger: "cancel", label: "Cancelar", icon: "cancel", tone: "neutral" },
  ],
  work: [
    { trigger: "complete", label: "Concluir", icon: "task_alt", tone: "primary" },
    { trigger: "hold", label: "Pausar", icon: "pause", tone: "neutral" },
    { trigger: "block", label: "Bloquear", icon: "block", tone: "danger" },
  ],
  review: [
    { trigger: "complete", label: "Aprovar", icon: "done_all", tone: "primary" },
    { trigger: "reopen", label: "Reabrir", icon: "restart_alt", tone: "neutral" },
  ],
  blocked: [
    { trigger: "reopen", label: "Reabrir", icon: "restart_alt", tone: "primary" },
    { trigger: "cancel", label: "Cancelar", icon: "cancel", tone: "neutral" },
  ],
  done: [{ trigger: "reopen", label: "Reabrir", icon: "restart_alt", tone: "neutral" }],
  cancelled: [{ trigger: "reopen", label: "Reabrir", icon: "restart_alt", tone: "neutral" }],
};

const TONE_CLASS: Record<"primary" | "neutral" | "danger", string> = {
  primary: "bg-primary text-primary-contrast hover:opacity-90",
  neutral: "bg-surface-container-high text-on-surface hover:bg-surface-container-highest",
  danger: "bg-status-blocked/15 text-status-blocked hover:bg-status-blocked/25",
};

// --- Helpers ---------------------------------------------------------------

function parseTags(tags: string | null | undefined): string[] {
  if (!tags) return [];
  return tags.split(",").map((t) => t.trim()).filter(Boolean);
}

/** Format an ISO timestamp into a compact pt-BR date-time, or "—" when absent. */
function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// --- Loading / error primitives -------------------------------------------

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-container-high/60 ${className}`} />;
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 rounded-2xl bg-surface-container-low p-6 shadow-sm">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-2/3" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-6 w-20" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Skeleton className="h-40 w-full rounded-2xl" />
          <Skeleton className="h-32 w-full rounded-2xl" />
        </div>
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry: () => void }) {
  const notFound = (error as ApiError)?.status === 404;
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container-low p-10 text-center shadow-sm">
      <span className="material-symbol text-[44px] text-status-blocked">{notFound ? "search_off" : "error"}</span>
      <div className="flex flex-col gap-1">
        <h2 className="font-display text-headline-sm text-on-surface">
          {notFound ? "Tarefa não encontrada" : "Não foi possível carregar a tarefa"}
        </h2>
        <p className="max-w-md text-body-sm text-on-surface-variant">
          {notFound
            ? "O item solicitado não existe ou foi removido. Volte ao Board e selecione outra tarefa."
            : error.message ||
              "Ocorreu um erro ao falar com o Orc. Verifique se o serviço está no ar e tente novamente."}
        </p>
      </div>
      {notFound ? (
        <Link
          to="/board"
          className="mt-1 flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-label-md font-semibold text-primary-contrast transition-opacity hover:opacity-90"
        >
          <span className="material-symbol text-[18px]">view_kanban</span>
          Ir para o Board
        </Link>
      ) : (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-label-md font-semibold text-primary-contrast transition-opacity hover:opacity-90"
        >
          <span className="material-symbol text-[18px]">refresh</span>
          Tentar novamente
        </button>
      )}
    </div>
  );
}

/** A labelled section card with an icon header and an optional count badge. */
function Section({
  icon,
  title,
  count,
  children,
}: {
  icon: string;
  title: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-2xl bg-surface-container-low p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="material-symbol text-[20px] text-primary">{icon}</span>
        <h2 className="font-display text-label-lg font-bold tracking-tight text-on-surface">{title}</h2>
        {typeof count === "number" ? (
          <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-sm font-bold text-on-surface-variant">
            {count}
          </span>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function SectionEmpty({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed border-surface-variant/60 px-3 py-6 text-center">
      <span className="material-symbol text-[22px] text-on-surface-variant">{icon}</span>
      <span className="text-label-sm text-on-surface-variant">{text}</span>
    </div>
  );
}

// --- Child row -------------------------------------------------------------

function ChildRow({ child }: { child: WorkItem }) {
  const sm = statusMeta(child.status);
  const pm = priorityMeta(child.priority);
  return (
    <Link
      to={`/task/${child.id}`}
      className="group flex items-center gap-2 rounded-xl bg-surface-container-low/60 px-3 py-2.5 transition-colors hover:bg-surface-container"
    >
      <span className="material-symbol flex-shrink-0 text-[18px] text-on-surface-variant">task_alt</span>
      <span className="min-w-0 flex-1 truncate text-body-md text-on-surface" title={child.title}>
        {child.title}
      </span>
      <span className={`hidden rounded px-1.5 py-0.5 text-label-sm font-bold md:inline ${pm.chip}`}>{pm.label}</span>
      <span className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-label-sm font-semibold ${sm.chip}`}>
        <span className={`h-1.5 w-1.5 rounded-full ${sm.dot}`} />
        {sm.label}
      </span>
      <span className="material-symbol text-[18px] text-on-surface-variant opacity-0 transition-opacity group-hover:opacity-100">
        chevron_right
      </span>
    </Link>
  );
}

// --- Dependency row --------------------------------------------------------

function DependencyRow({ edge, direction }: { edge: DependencyEdge; direction: "blocks" | "blocked_by" }) {
  // Outbound ("blocks") joins to_title/to_status + target id = to_id.
  // Inbound ("blocked_by") joins from_title/from_status + related id = from_id.
  const relatedId = direction === "blocks" ? edge.to_id : edge.from_id;
  const title = direction === "blocks" ? edge.to_title : edge.from_title;
  const status = direction === "blocks" ? edge.to_status : edge.from_status;
  const sm = status ? statusMeta(status) : null;
  return (
    <Link
      to={`/task/${relatedId}`}
      className="group flex items-center gap-2 rounded-xl bg-surface-container-low/60 px-3 py-2 transition-colors hover:bg-surface-container"
    >
      <span className="material-symbol flex-shrink-0 text-[16px] text-on-surface-variant">
        {direction === "blocks" ? "arrow_outward" : "arrow_cool_down"}
      </span>
      <span className="min-w-0 flex-1 truncate text-body-sm text-on-surface" title={title ?? relatedId}>
        {title ?? relatedId}
      </span>
      {sm ? (
        <span className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-label-sm font-semibold ${sm.chip}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${sm.dot}`} />
          {sm.label}
        </span>
      ) : null}
    </Link>
  );
}

// --- Note row --------------------------------------------------------------

function NoteRow({ note }: { note: ItemNote }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl bg-surface-container-low/60 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-label-sm font-semibold text-on-surface">
          <span className="material-symbol text-[14px] text-primary">sticky_note_2</span>
          {note.key}
          <span className="rounded bg-surface-container-high px-1.5 py-0.5 text-label-sm font-normal text-on-surface-variant">
            {note.role}
          </span>
        </span>
        <span className="text-label-sm text-on-surface-variant">{formatDateTime(note.updated_at)}</span>
      </div>
      {note.body ? (
        <p className="whitespace-pre-line text-body-sm text-on-surface-variant">{note.body}</p>
      ) : (
        <p className="text-body-sm italic text-on-surface-variant">(sem conteúdo)</p>
      )}
    </div>
  );
}

// --- Claim card ------------------------------------------------------------

function ClaimCard({ claim }: { claim: ClaimOwner | null }) {
  if (!claim) {
    return <SectionEmpty icon="lock_open" text="Ninguém reivindicou esta tarefa" />;
  }
  return (
    <div className="flex flex-col gap-2 rounded-xl bg-surface-container-low/60 p-3">
      <div className="flex items-center gap-2">
        <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-surface-container-high text-primary">
          <span className="material-symbol text-[18px]">verified_user</span>
        </div>
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-label-md font-bold text-on-surface" title={claim.label}>
            {claim.label}
          </span>
          <span className="truncate text-label-sm text-on-surface-variant">
            {claim.hostname}
            {claim.agent_id ? ` / ${claim.agent_id}` : ""} · {claim.cli}
          </span>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-label-sm">
        <dt className="text-on-surface-variant">Reivindicado</dt>
        <dd className="text-right text-on-surface">{formatDateTime(claim.claimed_at)}</dd>
        <dt className="text-on-surface-variant">Expira</dt>
        <dd className="text-right text-on-surface">{claim.expires_at ? formatDateTime(claim.expires_at) : "nunca"}</dd>
      </dl>
    </div>
  );
}

// --- Meta row --------------------------------------------------------------

function MetaRow({ icon, label, value }: { icon: string; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
        <span className="material-symbol text-[16px]">{icon}</span>
        {label}
      </span>
      <span className="truncate text-right text-label-md text-on-surface">{value}</span>
    </div>
  );
}

// --- Page ------------------------------------------------------------------

export default function TaskDetail() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);

  const detailQuery = useQuery<ItemDetail, ApiError>({
    queryKey: ["item", id],
    queryFn: () => getItemDetail(id),
    enabled: Boolean(id),
  });

  const advanceMutation = useMutation<WorkItem, ApiError, AdvanceTrigger>({
    mutationFn: (trigger) => advanceItem(id, trigger),
    onMutate: () => setActionError(null),
    onError: (err) => setActionError(err.message || "Não foi possível executar a ação."),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["item", id] });
      // Board / arcs lists reflect status changes too.
      void queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });

  const item = detailQuery.data;
  const actions = useMemo(() => (item ? ADVANCE_ACTIONS[item.status] ?? [] : []), [item]);
  const tags = useMemo(() => parseTags(item?.tags).filter((t) => t !== "arc"), [item?.tags]);

  const advancing = advanceMutation.isPending;
  const assignee = item?.updated_by ?? item?.created_by ?? null;

  return (
    <div className="flex w-full flex-col pb-10">
      {/* Back link */}
      <div className="flex items-center gap-2 py-4">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 rounded-xl bg-surface-container-high px-3 py-1.5 text-label-md text-on-surface transition-colors hover:bg-surface-container-highest"
        >
          <span className="material-symbol text-[18px]">arrow_back</span>
          Voltar
        </button>
        <Link
          to="/board"
          className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-label-md text-on-surface-variant transition-colors hover:text-on-surface"
        >
          <span className="material-symbol text-[16px]">view_kanban</span>
          Board
        </Link>
      </div>

      {detailQuery.isError ? (
        <ErrorState error={detailQuery.error} onRetry={() => void detailQuery.refetch()} />
      ) : detailQuery.isLoading || !item ? (
        <DetailSkeleton />
      ) : (
        <div className="flex flex-col gap-6">
          {/* Header card */}
          <div className="flex flex-col gap-3 rounded-2xl bg-surface-container-low p-6 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="text-label-sm font-bold uppercase tracking-widest text-primary">Tarefa</span>
              {item.item_type ? (
                <span className="rounded bg-surface-container-high px-1.5 py-0.5 text-label-sm text-on-surface-variant">
                  {item.item_type}
                </span>
              ) : null}
            </div>
            <div className="flex items-start gap-3">
              <span
                className={`mt-1.5 h-3 w-3 flex-shrink-0 rounded-full ${priorityMeta(item.priority).dot}`}
                title={`Prioridade: ${priorityMeta(item.priority).label}`}
              />
              <h1 className="font-display text-headline-lg font-extrabold tracking-tight text-on-surface">
                {item.title}
              </h1>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`flex items-center gap-1 rounded px-2 py-0.5 text-label-md font-semibold ${statusMeta(item.status).chip}`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${statusMeta(item.status).dot}`} />
                {statusMeta(item.status).label}
              </span>
              <span className={`rounded px-2 py-0.5 text-label-md font-bold ${priorityMeta(item.priority).chip}`}>
                {priorityMeta(item.priority).label}
              </span>
              {item.previous_status ? (
                <span className="flex items-center gap-1 rounded bg-surface-container-high px-2 py-0.5 text-label-sm text-on-surface-variant">
                  <span className="material-symbol text-[14px]">history</span>
                  antes: {statusMeta(item.previous_status).label}
                </span>
              ) : null}
              {tags.map((t) => (
                <span
                  key={t}
                  className="rounded bg-surface-container-high px-2 py-0.5 text-label-sm text-on-surface-variant"
                >
                  #{t}
                </span>
              ))}
            </div>

            {/* Advance actions */}
            {actions.length > 0 ? (
              <div className="mt-1 flex flex-wrap items-center gap-2">
                {actions.map((a) => (
                  <button
                    key={a.trigger}
                    type="button"
                    disabled={advancing}
                    onClick={() => advanceMutation.mutate(a.trigger)}
                    className={`flex items-center gap-1.5 rounded-xl px-3 py-2 text-label-md font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-40 ${TONE_CLASS[a.tone]}`}
                    title={`${a.label} esta tarefa`}
                  >
                    <span className="material-symbol text-[16px]">
                      {advancing ? "progress_activity" : a.icon}
                    </span>
                    {a.label}
                  </button>
                ))}
              </div>
            ) : null}
            {actionError ? (
              <div className="flex items-center gap-1.5 rounded-lg bg-status-blocked/15 px-3 py-2 text-label-sm text-status-blocked">
                <span className="material-symbol text-[16px]">error</span>
                {actionError}
              </div>
            ) : null}
          </div>

          {/* Two-column body: main (2/3) + sidebar (1/3) */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="flex flex-col gap-6 lg:col-span-2">
              {/* Description */}
              <Section icon="description" title="Descrição">
                {item.description ? (
                  <p className="whitespace-pre-line text-body-md text-on-surface-variant">{item.description}</p>
                ) : (
                  <SectionEmpty icon="notes" text="Sem descrição" />
                )}
                {item.summary ? (
                  <div className="mt-2 rounded-xl bg-surface-container-low/60 p-3">
                    <p className="mb-1 flex items-center gap-1 text-label-sm font-semibold text-on-surface-variant">
                      <span className="material-symbol text-[14px]">summarize</span>
                      Resumo
                    </p>
                    <p className="whitespace-pre-line text-body-sm text-on-surface-variant">{item.summary}</p>
                  </div>
                ) : null}
              </Section>

              {/* Subtasks (children) */}
              <Section icon="account_tree" title="Subtarefas" count={item.children.length}>
                {item.children.length === 0 ? (
                  <SectionEmpty icon="layers_clear" text="Nenhuma subtarefa" />
                ) : (
                  <div className="flex flex-col gap-1.5">
                    {item.children.map((c) => (
                      <ChildRow key={c.id} child={c} />
                    ))}
                  </div>
                )}
              </Section>

              {/* Dependencies */}
              <Section
                icon="link"
                title="Dependências"
                count={item.dependencies.blocks.length + item.dependencies.blocked_by.length}
              >
                {item.dependencies.blocks.length === 0 && item.dependencies.blocked_by.length === 0 ? (
                  <SectionEmpty icon="link_off" text="Nenhuma dependência" />
                ) : (
                  <div className="flex flex-col gap-4">
                    {item.dependencies.blocked_by.length > 0 ? (
                      <div className="flex flex-col gap-1.5">
                        <p className="flex items-center gap-1 text-label-sm font-semibold text-on-surface-variant">
                          <span className="material-symbol text-[14px] text-status-blocked">lock</span>
                          Bloqueada por ({item.dependencies.blocked_by.length})
                        </p>
                        {item.dependencies.blocked_by.map((e) => (
                          <DependencyRow key={e.id} edge={e} direction="blocked_by" />
                        ))}
                      </div>
                    ) : null}
                    {item.dependencies.blocks.length > 0 ? (
                      <div className="flex flex-col gap-1.5">
                        <p className="flex items-center gap-1 text-label-sm font-semibold text-on-surface-variant">
                          <span className="material-symbol text-[14px] text-primary">front_hand</span>
                          Bloqueia ({item.dependencies.blocks.length})
                        </p>
                        {item.dependencies.blocks.map((e) => (
                          <DependencyRow key={e.id} edge={e} direction="blocks" />
                        ))}
                      </div>
                    ) : null}
                  </div>
                )}
              </Section>

              {/* Notes */}
              <Section icon="comment" title="Notas" count={item.notes.length}>
                {item.notes.length === 0 ? (
                  <SectionEmpty icon="speaker_notes_off" text="Nenhuma nota registrada" />
                ) : (
                  <div className="flex flex-col gap-2">
                    {item.notes.map((n) => (
                      <NoteRow key={n.id} note={n} />
                    ))}
                  </div>
                )}
              </Section>
            </div>

            {/* Sidebar */}
            <div className="flex flex-col gap-6">
              {/* Claim */}
              <Section icon="how_to_reg" title="Reivindicação">
                <ClaimCard claim={item.claim} />
              </Section>

              {/* Authorship + metadata */}
              <Section icon="info" title="Detalhes">
                <div className="flex flex-col divide-y divide-surface-variant/30">
                  <MetaRow
                    icon={assignee ? "person" : "person_off"}
                    label="Responsável"
                    value={assignee ?? <span className="text-on-surface-variant">sem responsável</span>}
                  />
                  <MetaRow
                    icon="edit"
                    label="Atualizado por"
                    value={item.updated_by ?? <span className="text-on-surface-variant">—</span>}
                  />
                  <MetaRow
                    icon="person_add"
                    label="Criado por"
                    value={item.created_by ?? <span className="text-on-surface-variant">—</span>}
                  />
                  <MetaRow icon="schedule" label="Criado em" value={formatDateTime(item.created_at)} />
                  <MetaRow icon="update" label="Atualizado em" value={formatDateTime(item.updated_at)} />
                  {item.due_at ? (
                    <MetaRow icon="event" label="Prazo" value={formatDate(item.due_at)} />
                  ) : null}
                  {typeof item.complexity === "number" ? (
                    <MetaRow icon="speed" label="Complexidade" value={item.complexity} />
                  ) : null}
                  {item.parent_id ? (
                    <div className="flex items-center justify-between gap-3 py-1.5">
                      <span className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
                        <span className="material-symbol text-[16px]">subdirectory_arrow_right</span>
                        Item pai
                      </span>
                      <Link
                        to={`/task/${item.parent_id}`}
                        className="flex items-center gap-1 text-label-md text-primary hover:text-primary-fixed-dim"
                      >
                        abrir
                        <span className="material-symbol text-[14px]">open_in_new</span>
                      </Link>
                    </div>
                  ) : null}
                  <MetaRow
                    icon="tag"
                    label="ID"
                    value={<span className="font-mono text-label-sm">{item.id}</span>}
                  />
                </div>
              </Section>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
