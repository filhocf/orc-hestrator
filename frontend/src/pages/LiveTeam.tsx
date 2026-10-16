import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSessions } from "@/api/client";
import type { ApiError } from "@/api/client";
import type { Session } from "@/api/types";

/**
 * Time ao vivo (Live team presence) — screen 3, the product's signature view.
 * Ported from the Stitch mockup (the official variant 3):
 *   docs/design/stitch/time_ao_vivo_orc_hestrator_3/code.html
 *
 * HONESTY CONTRACT — only REAL fields from GET /api/sessions are rendered.
 * Shape confirmed live (http://127.0.0.1:8005/api/sessions), each item has:
 *   { agent_id, hostname, pid, cli, theme, status, started_at,
 *     heartbeat_at, session_id, label }
 *
 * The mockup fabricates CPU %, memory, tokens/s, latency ms, a progress bar,
 * per-agent task descriptions and specialist roles, host uptime % and action
 * buttons (ping / pause / inspect). NONE of those are backed by the API, so
 * they are deliberately OMITTED rather than invented.
 *
 * What is derived from REAL timestamps:
 *   - "ativo há Xm"  -> now - started_at
 *   - heartbeat freshness ("há Xs" + liveness dot) -> now - heartbeat_at
 *   - liveness bucket (Ativo / Inativo) -> heartbeat age threshold
 *
 * Presence feels "live" via react-query refetchInterval (5s).
 */

const REFETCH_MS = 5000;
// A session whose last heartbeat is older than this is treated as "Inativo".
const STALE_HEARTBEAT_MS = 60_000;

type Liveness = "ativo" | "inativo";

interface GroupedHost {
  hostname: string;
  sessions: Session[];
}

// --- Time helpers (all computed from REAL timestamps) ---------------------

function parseTs(iso: string): number {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? 0 : t;
}

/** Compact pt-BR "age" label from an ISO timestamp to now. */
function humanizeAge(iso: string, now: number): string {
  const ms = now - parseTs(iso);
  if (!parseTs(iso) || ms < 0) return "—";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function liveness(session: Session, now: number): Liveness {
  const age = now - parseTs(session.heartbeat_at);
  return parseTs(session.heartbeat_at) && age <= STALE_HEARTBEAT_MS ? "ativo" : "inativo";
}

/** Short session id for the mono pill, e.g. "sess-06a01ba0". */
function shortSession(session: Session): string {
  const head = session.session_id?.split("-")[0] ?? session.session_id ?? "";
  return head ? `sess-${head}` : "sess-?";
}

/** Two-letter avatar initials from the agent id (or host when anonymous). */
function initials(session: Session): string {
  const base = session.agent_id ?? session.hostname ?? "?";
  const clean = base.replace(/[^a-zA-Z0-9]/g, "");
  return (clean.slice(0, 2) || "?").toLowerCase();
}

/** Classify the client string into a friendly actor kind + label. */
function actorKind(cli: string): { isHuman: boolean; badge: string } {
  const isHuman = cli.toLowerCase() === "humano";
  return { isHuman, badge: isHuman ? "Humano" : "Agente IA" };
}

// --- Loading / empty / error primitives -----------------------------------

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-container-high/60 ${className}`} />;
}

function HostSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      {[0, 1].map((h) => (
        <div key={h} className="flex flex-col gap-4">
          <Skeleton className="h-12 w-full" />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {[0, 1].map((c) => (
              <div key={c} className="rounded-2xl bg-surface-container p-4 shadow-sm">
                <Skeleton className="mb-4 h-11 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container p-10 text-center shadow-sm">
      <span className="material-symbol text-[44px] text-status-blocked">sensors_off</span>
      <div className="flex flex-col gap-1">
        <h2 className="font-display text-headline-sm text-on-surface">Não foi possível carregar a presença ao vivo</h2>
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

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-surface-container p-16 text-center shadow-sm">
      <span className="material-symbol text-[48px] text-on-surface-variant">sensors_off</span>
      <div className="flex flex-col gap-0.5">
        <p className="text-body-lg font-medium text-on-surface">Nenhuma sessão ativa no momento</p>
        <p className="max-w-sm text-body-sm text-on-surface-variant">
          Hosts, agentes e humanos aparecerão aqui assim que registrarem uma sessão e enviarem heartbeat.
        </p>
      </div>
    </div>
  );
}

// --- Actor card (one session) ---------------------------------------------

function ActorCard({ session, now }: { session: Session; now: number }) {
  const live = liveness(session, now);
  const { isHuman, badge } = actorKind(session.cli);
  const displayName = session.agent_id ?? "(anônimo)";

  // Top accent bar: teal gradient for live sessions, muted for stale ones.
  const accent = live === "ativo" ? "bg-gradient-to-r from-tertiary to-primary" : "bg-surface-variant";
  const badgeClass = isHuman
    ? "bg-secondary-container text-secondary"
    : "bg-primary/10 text-primary";
  const avatarClass = isHuman ? "text-secondary" : "text-primary";

  return (
    <div className="actor-card relative flex flex-col justify-between overflow-hidden rounded-2xl bg-surface-container p-4 shadow-sm transition-all duration-200 hover:bg-surface-container-high/60">
      <div className={`absolute left-0 right-0 top-0 h-1 ${accent}`} />
      <div className="flex flex-col gap-4">
        {/* Header: identity + session pill */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div
              className={`flex h-11 w-11 items-center justify-center rounded-xl bg-surface-container-highest font-display text-headline-sm font-bold shadow-sm ${avatarClass}`}
            >
              {isHuman ? <span className="material-symbol text-[22px]">person</span> : initials(session)}
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="font-display text-headline-sm font-bold tracking-tight text-on-surface">
                  {displayName}
                </span>
                <span className={`rounded px-2 py-0.5 text-label-sm font-bold ${badgeClass}`}>{badge}</span>
              </div>
              <span className="text-body-sm text-on-surface-variant">
                PID <span className="font-mono">{session.pid}</span>
              </span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className="rounded bg-surface-container-lowest px-2 py-0.5 font-mono text-label-sm text-on-surface-variant">
              {shortSession(session)}
            </span>
            <span
              className={`flex items-center gap-1 font-mono text-label-sm ${
                live === "ativo" ? "text-tertiary" : "text-on-surface-variant"
              }`}
            >
              <span className="material-symbol text-[14px]">bolt</span>
              {humanizeAge(session.heartbeat_at, now)}
            </span>
          </div>
        </div>

        {/* Status box — liveness derived from real heartbeat/started_at */}
        <div className="flex flex-col gap-2 rounded-xl bg-surface-container-lowest p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {live === "ativo" ? (
                <span className="relative flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-tertiary opacity-75" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-tertiary" />
                </span>
              ) : (
                <span className="h-2.5 w-2.5 rounded-full bg-surface-variant" />
              )}
              <span
                className={`text-label-md font-bold ${
                  live === "ativo" ? "text-tertiary" : "text-on-surface-variant"
                }`}
              >
                {live === "ativo" ? "Sessão ativa" : "Sem heartbeat recente"}
              </span>
            </div>
            <span className="text-label-sm text-on-surface-variant">Ativo há {humanizeAge(session.started_at, now)}</span>
          </div>
          <p className="text-body-sm leading-snug text-on-surface-variant">
            Identificador completo:{" "}
            <span className="break-all font-mono text-on-surface">{session.session_id}</span>
          </p>
        </div>

        {/* Client / host facts — only real fields */}
        <div className="grid grid-cols-2 gap-2 pt-1">
          <div className="flex flex-col rounded-lg bg-surface-container-low p-2">
            <span className="truncate text-label-sm text-on-surface-variant">Cliente</span>
            <span className="truncate font-mono text-label-md font-semibold text-on-surface">{session.cli}</span>
          </div>
          <div className="flex flex-col rounded-lg bg-surface-container-low p-2">
            <span className="truncate text-label-sm text-on-surface-variant">Host</span>
            <span className="truncate text-label-md font-semibold text-on-surface">{session.hostname}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Host group ------------------------------------------------------------

function HostGroup({ group, now }: { group: GroupedHost; now: number }) {
  const liveCount = group.sessions.filter((s) => liveness(s, now) === "ativo").length;
  return (
    <div className="host-group flex flex-col gap-4" data-host={group.hostname}>
      {/* Host header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-surface-container px-4 py-3 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-container-highest text-primary">
            <span className="material-symbol text-[20px]">hard_drive</span>
          </div>
          <span className="font-display text-label-lg font-bold tracking-tight text-on-surface">
            {group.hostname}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center rounded-full bg-surface-container-high px-2.5 py-0.5 text-label-sm font-bold text-on-surface-variant">
            {group.sessions.length} {group.sessions.length === 1 ? "sessão" : "sessões"}
          </span>
          {liveCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-tertiary/10 px-2.5 py-0.5 text-label-sm font-semibold text-tertiary">
              <span className="h-1.5 w-1.5 rounded-full bg-tertiary" />
              {liveCount} ativa{liveCount === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {group.sessions.map((s) => (
          <ActorCard key={s.session_id} session={s} now={now} />
        ))}
      </div>
    </div>
  );
}

// --- Page ------------------------------------------------------------------

export default function LiveTeam() {
  const [filter, setFilter] = useState("");

  const sessionsQuery = useQuery<Session[], ApiError>({
    queryKey: ["sessions", "live"],
    queryFn: () => getSessions(),
    refetchInterval: REFETCH_MS,
  });

  // A single "now" per render keeps every relative time consistent.
  const now = Date.now();
  const sessions = useMemo(() => sessionsQuery.data ?? [], [sessionsQuery.data]);

  // Client-side quick filter over host / agent / session (the API also
  // supports ?hostname= / ?agent_id=, but a free-text field matches any).
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) =>
      [s.hostname, s.agent_id ?? "", s.session_id, s.cli, s.label]
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  }, [sessions, filter]);

  // Group by host, hosts sorted alphabetically for a stable layout.
  const groups = useMemo<GroupedHost[]>(() => {
    const map = new Map<string, Session[]>();
    for (const s of filtered) {
      const list = map.get(s.hostname) ?? [];
      list.push(s);
      map.set(s.hostname, list);
    }
    return [...map.entries()]
      .map(([hostname, list]) => ({ hostname, sessions: list }))
      .sort((a, b) => a.hostname.localeCompare(b.hostname));
  }, [filtered]);

  const agentsOnline = sessions.filter((s) => s.agent_id && actorKind(s.cli).isHuman === false).length;
  const humansOnline = sessions.filter((s) => actorKind(s.cli).isHuman).length;

  return (
    <div className="flex w-full flex-col pb-10">
      {/* Telemetry header */}
      <div className="mb-6 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <span className="material-symbol text-[18px]">sensors</span>
            </span>
            <span className="text-label-sm font-bold uppercase tracking-widest text-primary">
              Presença em tempo real
            </span>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <h1 className="font-display text-headline-lg font-extrabold tracking-tight text-on-surface">
              Time ao vivo
            </h1>
            <div className="flex items-center gap-2 rounded-full bg-surface-container-high px-3 py-1 shadow-sm">
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-tertiary" />
              <span className="text-label-md text-on-surface">
                Online agora: <strong className="font-bold text-tertiary">{agentsOnline} agentes</strong> •{" "}
                <strong className="font-bold text-primary">{humansOnline} humanos</strong>
              </span>
            </div>
          </div>
        </div>

        {/* Filter bar — wired to the real session list */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[260px] flex-1">
            <span className="material-symbol absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant">
              filter_list
            </span>
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              aria-label="Filtrar por host, agente ou sessão"
              placeholder="Filtrar por host, agente ou sessão..."
              className="w-full rounded-xl bg-surface-container py-2 pl-9 pr-3 text-body-sm text-on-surface outline-none transition-all placeholder:text-on-surface-variant focus:bg-surface-container-high"
            />
          </div>
          {sessionsQuery.isFetching && !sessionsQuery.isLoading && (
            <span className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
              <span className="material-symbol animate-spin text-[16px]">progress_activity</span>
              Atualizando…
            </span>
          )}
        </div>
      </div>

      {/* Body */}
      {sessionsQuery.isError ? (
        <ErrorState error={sessionsQuery.error} onRetry={() => void sessionsQuery.refetch()} />
      ) : sessionsQuery.isLoading ? (
        <HostSkeleton />
      ) : groups.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="flex flex-col gap-8">
          {groups.map((g) => (
            <HostGroup key={g.hostname} group={g} now={now} />
          ))}
        </div>
      )}
    </div>
  );
}
