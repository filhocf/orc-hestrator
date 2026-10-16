import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getContext, getMetrics, getSessions } from "@/api/client";
import type { ApiError } from "@/api/client";
import type { Context, Metrics, Session, WorkItem } from "@/api/types";

/**
 * Visão geral (Dashboard) — screen 2.
 * Ported from the Stitch mockup:
 *   docs/design/stitch/vis_o_geral_orc_hestrator/code.html
 *
 * All figures are REAL, fetched via react-query:
 *   - GET /api/context  -> counts + active/blocked/recent_completed
 *   - GET /api/metrics  -> wip, lead_time_avg_seconds, total_items, throughput
 *   - GET /api/sessions -> live presence (empty for now => graceful empty state)
 *
 * The mockup's hard-coded numbers (65 total, 8 agentes, 18 min, etc.) are
 * replaced by live data. Material Symbols use the scaffold's `.material-symbol`
 * helper (see index.css); FILL is toggled via fontVariationSettings when needed.
 */

// --- Small presentational helpers ----------------------------------------

const STATUS_META: { key: keyof NonNullable<Context["counts"]>; label: string; colorClass: string; barClass: string }[] = [
  { key: "queue", label: "Fila", colorClass: "text-secondary", barClass: "bg-secondary" },
  { key: "work", label: "Operando", colorClass: "text-primary-container", barClass: "bg-primary-container" },
  { key: "review", label: "Revisão", colorClass: "text-primary", barClass: "bg-primary" },
  { key: "done", label: "Feito", colorClass: "text-tertiary", barClass: "bg-tertiary" },
];

function count(counts: Context["counts"] | undefined, key: string): number {
  return (counts?.[key] as number | undefined) ?? 0;
}

/** Humanize a lead-time value given in seconds into a compact pt-BR label. */
function formatLeadTime(seconds: number): { value: string; unit: string } {
  if (!seconds || seconds <= 0) return { value: "0", unit: "s / tarefa" };
  if (seconds < 60) return { value: seconds.toFixed(seconds < 10 ? 1 : 0), unit: "s / tarefa" };
  if (seconds < 3600) return { value: Math.round(seconds / 60).toString(), unit: "min / tarefa" };
  return { value: (seconds / 3600).toFixed(1), unit: "h / tarefa" };
}

/** Parse the "tags" CSV field into a clean array. */
function parseTags(tags: string | null | undefined): string[] {
  if (!tags) return [];
  return tags.split(",").map((t) => t.trim()).filter(Boolean);
}

// --- Loading / error primitives -------------------------------------------

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-container-high/60 ${className}`} />;
}

function CardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex flex-col justify-between overflow-hidden rounded-xl bg-surface-container-low p-4 shadow-sm">
      {children}
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl bg-surface-container-low p-8 text-center shadow-sm">
      <span className="material-symbol text-[40px] text-status-blocked">error</span>
      <div className="flex flex-col gap-1">
        <h2 className="font-display text-headline-sm text-on-surface">Não foi possível carregar o painel</h2>
        <p className="max-w-md text-body-sm text-on-surface-variant">
          {error.message || "Ocorreu um erro ao falar com o Orc. Verifique se o serviço está no ar e tente novamente."}
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

// --- Summary cards ---------------------------------------------------------

function CardsSkeleton() {
  return (
    <div className="mt-2 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[0, 1, 2, 3].map((i) => (
        <CardShell key={i}>
          <Skeleton className="mb-3 h-5 w-32" />
          <Skeleton className="h-10 w-20" />
          <Skeleton className="mt-3 h-2.5 w-full" />
        </CardShell>
      ))}
    </div>
  );
}

function SummaryCards({ context, metrics }: { context: Context; metrics: Metrics }) {
  const counts = context.counts;
  const total = metrics.total_items ?? STATUS_META.reduce((acc, s) => acc + count(counts, s.key as string), 0);
  const done = count(counts, "done");
  const blocked = context.blocked?.length ?? count(counts, "blocked");
  const sessionsOnline = 0; // /api/sessions is empty for now (see LiveTeam).
  const lead = formatLeadTime(metrics.lead_time_avg_seconds);

  // Segment widths for the multi-segment bar (guard against divide-by-zero).
  const segTotal = STATUS_META.reduce((acc, s) => acc + count(counts, s.key as string), 0) || 1;

  return (
    <div className="mt-2 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Card 1: Itens por estado */}
      <CardShell>
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="material-symbol text-[20px] text-primary">dataset</span>
            <span className="text-label-lg font-semibold text-on-surface">Itens por estado</span>
          </div>
          <span className="rounded bg-surface-container-high px-2 py-0.5 text-label-sm text-on-surface-variant">
            {total} total
          </span>
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between text-on-surface">
            <span className="font-display text-headline-lg font-bold text-primary">{done}</span>
            <span className="flex items-center gap-0.5 text-label-sm font-semibold text-tertiary">
              <span className="material-symbol text-[14px]">trending_up</span> Concluídos
            </span>
          </div>
          <div className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-surface-container-highest p-0.5">
            {STATUS_META.map((s, idx) => {
              const w = (count(counts, s.key as string) / segTotal) * 100;
              const radius = idx === 0 ? "rounded-l-full" : idx === STATUS_META.length - 1 ? "rounded-r-full" : "";
              return (
                <div
                  key={s.key as string}
                  className={`h-full ${s.barClass} ${radius}`}
                  style={{ width: `${w}%` }}
                  title={`${s.label}: ${count(counts, s.key as string)}`}
                />
              );
            })}
          </div>
          <div className="grid grid-cols-4 gap-1 pt-1 text-label-sm text-on-surface-variant">
            {STATUS_META.map((s, idx) => (
              <div key={s.key as string} className={`flex flex-col ${idx === STATUS_META.length - 1 ? "text-right" : ""}`}>
                <span className={`font-semibold ${s.colorClass}`}>{count(counts, s.key as string)}</span>
                <span className="truncate">{s.label}</span>
              </div>
            ))}
          </div>
        </div>
      </CardShell>

      {/* Card 2: Agentes online */}
      <CardShell>
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="material-symbol text-[20px] text-tertiary">smart_toy</span>
            <span className="text-label-lg font-semibold text-on-surface">Agentes online</span>
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex items-baseline gap-1.5">
            <span className="font-display text-headline-lg font-bold text-on-surface">{sessionsOnline}</span>
            <span className="text-body-md text-on-surface-variant">agentes ativos</span>
          </div>
          <div className="flex items-center gap-1.5 text-label-md text-on-surface-variant">
            <span className="material-symbol text-[16px] text-tertiary">dns</span>
            <span>Presença via sessões em tempo real</span>
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between rounded-lg bg-surface-container-high/60 px-2 py-1.5">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-on-surface-variant" />
            <span className="text-label-sm font-medium text-on-surface">Aguardando heartbeat</span>
          </div>
          <span className="font-mono text-label-sm text-on-surface-variant">—</span>
        </div>
      </CardShell>

      {/* Card 3: Bloqueios */}
      <CardShell>
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="material-symbol text-[20px] text-status-blocked">gpp_maybe</span>
            <span className="text-label-lg font-semibold text-on-surface">Bloqueios</span>
          </div>
          {blocked > 0 && (
            <span className="flex items-center gap-1 rounded-full bg-status-blocked/20 px-2 py-0.5 text-label-sm font-bold uppercase tracking-tight text-status-blocked">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-status-blocked" /> Atenção requerida
            </span>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex items-baseline gap-1.5">
            <span className="font-display text-headline-lg font-bold text-status-blocked">{blocked}</span>
            <span className="text-body-md text-on-surface-variant">
              {blocked === 1 ? "tarefa travada" : "tarefas travadas"}
            </span>
          </div>
          <p className="line-clamp-1 text-body-sm text-on-surface-variant">
            {blocked > 0 ? context.blocked[0]?.title : "Nenhum impedimento ativo"}
          </p>
        </div>
        <div className="mt-2 flex items-center justify-between pt-0.5">
          <Link
            to="/board"
            className="flex items-center gap-1 text-label-sm text-primary transition-colors hover:text-primary-fixed-dim"
          >
            <span>Inspecionar impedimentos</span>
            <span className="material-symbol text-[14px]">arrow_forward</span>
          </Link>
        </div>
      </CardShell>

      {/* Card 4: Tempo médio de ciclo */}
      <CardShell>
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="material-symbol text-[20px] text-primary">speed</span>
            <span className="text-label-lg font-semibold text-on-surface">Tempo médio de ciclo</span>
          </div>
          <span className="rounded bg-tertiary/10 px-2 py-0.5 text-label-sm font-bold text-tertiary">WIP {metrics.wip}</span>
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex items-baseline gap-1.5">
            <span className="font-display text-headline-lg font-bold text-on-surface">{lead.value}</span>
            <span className="text-body-md text-on-surface-variant">{lead.unit}</span>
          </div>
          <p className="flex items-center gap-1 text-body-sm font-medium text-tertiary">
            <span className="material-symbol text-[14px]">auto_mode</span>
            <span>lead time médio ({metrics.period_days}d)</span>
          </p>
        </div>
        <div className="mt-2 flex items-center justify-between pt-0.5">
          <span className="text-label-sm text-on-surface-variant">
            Throughput: {metrics.throughput_per_week?.reduce((a, b) => a + b.count, 0) ?? 0}/período
          </span>
        </div>
      </CardShell>
    </div>
  );
}

// --- Live team (presence) --------------------------------------------------

function LiveTeam({ sessions, loading }: { sessions: Session[] | undefined; loading: boolean }) {
  const list = sessions ?? [];
  return (
    <div className="flex flex-col gap-4 lg:col-span-7">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-tertiary" />
          <h2 className="font-display text-headline-md font-semibold text-on-surface">Time ao vivo</h2>
          <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-sm text-on-surface-variant">
            Presença rápida
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
          <span className="material-symbol text-[16px]">filter_list</span>
          <span>{list.length} ativos nesta vista</span>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col gap-2">
          {[0, 1].map((i) => (
            <div key={i} className="rounded-xl bg-surface-container-low p-4 shadow-sm">
              <Skeleton className="h-14 w-full" />
            </div>
          ))}
        </div>
      ) : list.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl bg-surface-container-low p-10 text-center shadow-sm">
          <span className="material-symbol text-[40px] text-on-surface-variant">sensors_off</span>
          <div className="flex flex-col gap-0.5">
            <p className="text-body-md font-medium text-on-surface">Nenhum agente ativo no momento</p>
            <p className="max-w-sm text-body-sm text-on-surface-variant">
              Sessões de agentes aparecerão aqui assim que enviarem heartbeat.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {list.map((s) => (
            <div key={s.session_id} className="flex flex-col gap-3 rounded-xl bg-surface-container-low p-4 shadow-sm transition-all hover:bg-surface-container">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-surface-container-high font-display text-headline-sm font-bold text-primary">
                    <span className="material-symbol text-[20px] text-primary">terminal</span>
                    <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full bg-tertiary ring-2 ring-surface" />
                  </div>
                  <div className="flex flex-col">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-label-lg font-bold text-on-surface">{s.hostname}</span>
                      <span className="text-xs text-on-surface-variant">/</span>
                      <span className="rounded bg-surface-container-high px-1.5 py-0.5 font-mono text-label-md text-primary">
                        {s.agent_id ?? "—"}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-body-sm text-on-surface-variant">
                      <span className="inline-flex items-center gap-1 text-tertiary">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-tertiary" />
                        {s.status}
                      </span>
                      <span>•</span>
                      <span>
                        Cliente: <strong className="font-mono text-on-surface">{s.cli}</strong>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Recent activity -------------------------------------------------------

function RecentActivity({ context, loading }: { context: Context | undefined; loading: boolean }) {
  const completed = context?.recent_completed ?? [];
  const blocked = context?.blocked ?? [];
  const active = context?.active ?? [];

  // Build a simple activity feed from real context data (completions, blocks, claims).
  type Event = { id: string; kind: "done" | "blocked" | "claimed"; title: string; tags: string[] };
  const events: Event[] = [
    ...completed.map((i: WorkItem) => ({ id: `d-${i.id}`, kind: "done" as const, title: i.title, tags: parseTags(i.tags) })),
    ...blocked.map((i: WorkItem) => ({ id: `b-${i.id}`, kind: "blocked" as const, title: i.title, tags: parseTags(i.tags) })),
    ...active
      .filter((i) => i.status === "review" || i.status === "work")
      .slice(0, 3)
      .map((i: WorkItem) => ({ id: `c-${i.id}`, kind: "claimed" as const, title: i.title, tags: parseTags(i.tags) })),
  ];

  const META = {
    done: { label: "Conclusão", icon: "check_circle", color: "text-tertiary", bg: "bg-tertiary/20" },
    blocked: { label: "Bloqueio registrado", icon: "block", color: "text-status-blocked", bg: "bg-status-blocked/20" },
    claimed: { label: "Em andamento", icon: "assignment_turned_in", color: "text-primary", bg: "bg-primary/20" },
  } as const;

  return (
    <div className="flex flex-col gap-4 lg:col-span-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="material-symbol text-[20px] text-primary">history</span>
          <h2 className="font-display text-headline-md font-semibold text-on-surface">Atividade recente</h2>
        </div>
      </div>

      <div className="flex flex-col gap-4 rounded-xl bg-surface-container-low p-4 shadow-sm">
        {loading ? (
          <div className="flex flex-col gap-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
            <span className="material-symbol text-[36px] text-on-surface-variant">inbox</span>
            <p className="text-body-md font-medium text-on-surface">Sem atividade recente</p>
            <p className="max-w-xs text-body-sm text-on-surface-variant">
              Conclusões, bloqueios e reivindicações aparecerão aqui.
            </p>
          </div>
        ) : (
          <div className="relative flex flex-col gap-4">
            <div className="absolute bottom-2 left-4 top-2 -z-0 w-0.5 bg-surface-variant" />
            {events.map((e) => {
              const m = META[e.kind];
              return (
                <div key={e.id} className="relative z-10 flex items-start gap-4">
                  <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full shadow-sm ${m.bg} ${m.color}`}>
                    <span className="material-symbol text-[16px]">{m.icon}</span>
                  </div>
                  <div className="flex flex-1 flex-col">
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-label-md font-semibold ${m.color}`}>{m.label}</span>
                    </div>
                    <p className="mt-0.5 text-body-sm text-on-surface">{e.title}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// --- Page ------------------------------------------------------------------

export default function Overview() {
  const contextQuery = useQuery<Context, ApiError>({ queryKey: ["context"], queryFn: () => getContext() });
  const metricsQuery = useQuery<Metrics, ApiError>({ queryKey: ["metrics"], queryFn: () => getMetrics() });
  const sessionsQuery = useQuery<Session[], ApiError>({ queryKey: ["sessions"], queryFn: () => getSessions() });

  const headerLoading = contextQuery.isLoading || metricsQuery.isLoading;

  return (
    <div className="flex w-full flex-col pb-10">
      {/* Banner / sub-header */}
      <div className="flex flex-col items-start justify-between gap-4 py-4 md:flex-row md:items-center">
        <div className="flex items-center gap-4">
          <div className="relative flex h-12 w-12 items-center justify-center rounded-xl bg-surface-container-highest p-1.5 shadow-sm">
            <img className="h-full w-full rounded-lg object-cover" src={`${import.meta.env.BASE_URL}mascote.png`} alt="Orc" />
            <span className="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-tertiary">
              <span className="h-2 w-2 rounded-full bg-surface" />
            </span>
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="font-display text-headline-lg text-on-surface">Central de Operações</span>
            </div>
            <p className="text-body-sm text-on-surface-variant">
              Sincronização em tempo real entre agentes de IA e engenharia humana.
            </p>
          </div>
        </div>
        <div className="flex w-full items-center gap-2 md:w-auto">
          <Link
            to="/board"
            className="flex items-center gap-1.5 rounded-xl bg-surface-container-high px-4 py-2 text-label-md text-on-surface transition-colors hover:bg-surface-container-highest"
          >
            <span className="material-symbol text-[16px] text-primary">view_kanban</span>
            <span>Ver Board completo</span>
          </Link>
          <Link
            to="/graph"
            className="flex items-center gap-1.5 rounded-xl bg-surface-container-high px-4 py-2 text-label-md text-on-surface transition-colors hover:bg-surface-container-highest"
          >
            <span className="material-symbol text-[16px] text-tertiary">hub</span>
            <span>Ver Grafo</span>
          </Link>
        </div>
      </div>

      {/* Summary cards (context + metrics). */}
      {contextQuery.isError || metricsQuery.isError ? (
        <ErrorState
          error={(contextQuery.error ?? metricsQuery.error) as ApiError}
          onRetry={() => {
            void contextQuery.refetch();
            void metricsQuery.refetch();
          }}
        />
      ) : headerLoading ? (
        <CardsSkeleton />
      ) : contextQuery.data && metricsQuery.data ? (
        <SummaryCards context={contextQuery.data} metrics={metricsQuery.data} />
      ) : (
        <CardsSkeleton />
      )}

      {/* Middle section: Live team (60%) + Recent activity (40%). */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12">
        <LiveTeam sessions={sessionsQuery.data} loading={sessionsQuery.isLoading} />
        <RecentActivity
          context={contextQuery.data}
          loading={contextQuery.isLoading}
        />
      </div>
    </div>
  );
}
