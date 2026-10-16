import { useQuery } from "@tanstack/react-query";
import { getWorkspaces } from "@/api/client";
import type { ApiError } from "@/api/client";
import type { Workspace, WorkspacesMap } from "@/api/types";

/**
 * Administração / RBAC — screen 8.
 * Ported from the Stitch mockup intent:
 *   docs/design/stitch/administra_o_rbac_orc_hestrator/code.html
 *
 * HONESTY CONTRACT — this screen has TWO sections with very different footing:
 *
 *   1. WORKSPACES (REAL): GET /api/workspaces. The backend returns a MAP keyed
 *      by workspace name (workspace.list_workspaces()), `{}` when none exist
 *      (the current live state). We list name + description + tags + repos.
 *      Empty => a clear "Nenhum workspace configurado" state.
 *
 *   2. USUÁRIOS & PAPÉIS (STUB — FUTURE): there is NO users/roles management
 *      endpoint yet. Session auth/RBAC IS real now (F2: login/session/me +
 *      ProtectedRoute + role-based sidebar), but managing users/roles from this
 *      screen is future work. We render the section as UI but flag it
 *      unmistakably with an "Em breve" badge and a note, plus a
 *      demonstration-only sample table clearly labelled as mock.
 *      Nothing here is backed by the API — do NOT read it as real data.
 *
 * TODO: users/roles MANAGEMENT API = futuro. When it lands, replace the mock
 * table with a real query and drop the "Em breve" banner.
 */

// --- Loading / error primitives (same visual language as Overview) --------

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-container-high/60 ${className}`} />;
}

function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl bg-surface-container-low p-8 text-center shadow-sm">
      <span className="material-symbol text-[40px] text-status-blocked">error</span>
      <div className="flex flex-col gap-1">
        <h2 className="font-display text-headline-sm text-on-surface">
          Não foi possível carregar os workspaces
        </h2>
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

// --- Section header -------------------------------------------------------

function SectionHeader({
  icon,
  title,
  subtitle,
  badge,
}: {
  icon: string;
  title: string;
  subtitle: string;
  badge?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start gap-3">
      <span className="material-symbol mt-0.5 text-[24px] text-primary">{icon}</span>
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-headline-sm text-on-surface">{title}</h2>
          {badge}
        </div>
        <p className="text-body-sm text-on-surface-variant">{subtitle}</p>
      </div>
    </div>
  );
}

/** Amber "Em breve" pill used to mark the not-yet-real RBAC section. */
function SoonBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-primary-container/20 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-primary-container">
      <span className="material-symbol text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>
        schedule
      </span>
      Em breve
    </span>
  );
}

// --- Workspaces (REAL) ----------------------------------------------------

/** Hoist the workspace map into a sorted array for rendering. */
function toList(map: WorkspacesMap): Workspace[] {
  return Object.entries(map)
    .map(([name, cfg]) => ({ name, ...cfg }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function Chip({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "accent" }) {
  const cls =
    tone === "accent"
      ? "bg-primary/15 text-primary"
      : "bg-surface-container-high text-on-surface-variant";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-medium ${cls}`}>
      {children}
    </span>
  );
}

function WorkspaceCard({ ws }: { ws: Workspace }) {
  const tags = ws.tags ?? [];
  const repos = ws.repos ?? [];
  return (
    <div className="flex flex-col gap-3 rounded-xl bg-surface-container-low p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="material-symbol text-[20px] text-primary">folder_managed</span>
          <h3 className="font-display text-title-md text-on-surface">{ws.name}</h3>
        </div>
      </div>
      {ws.description ? (
        <p className="text-body-sm text-on-surface-variant">{ws.description}</p>
      ) : (
        <p className="text-body-sm italic text-on-surface-variant/70">Sem descrição.</p>
      )}

      {tags.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-label-sm font-semibold uppercase tracking-wide text-on-surface-variant">
            Tags
          </span>
          <div className="flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <Chip key={t} tone="accent">
                {t}
              </Chip>
            ))}
          </div>
        </div>
      )}

      {repos.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-label-sm font-semibold uppercase tracking-wide text-on-surface-variant">
            Repositórios
          </span>
          <div className="flex flex-wrap gap-1.5">
            {repos.map((r) => (
              <Chip key={r}>
                <span className="material-symbol mr-1 text-[14px]">database</span>
                {r}
              </Chip>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function WorkspacesEmpty() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-surface-border bg-surface-container-low/50 p-10 text-center">
      <span className="material-symbol text-[40px] text-content-subtle">folder_off</span>
      <h3 className="font-display text-title-md text-on-surface">Nenhum workspace configurado</h3>
      <p className="max-w-md text-body-sm text-on-surface-variant">
        Workspaces organizam itens por projeto (tags, repos, convenções). Quando algum for criado
        via <code className="rounded bg-surface-container-high px-1 py-0.5 text-[12px]">manage_workspaces</code>,
        ele aparece aqui.
      </p>
    </div>
  );
}

function WorkspacesSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex flex-col gap-3 rounded-xl bg-surface-container-low p-4 shadow-sm">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-6 w-40" />
        </div>
      ))}
    </div>
  );
}

function WorkspacesSection() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => getWorkspaces(),
  });

  return (
    <section className="rounded-2xl bg-surface-container/40 p-5">
      <SectionHeader
        icon="workspaces"
        title="Workspaces"
        subtitle="Projetos reais configurados no Orc (GET /api/workspaces)."
      />
      {isLoading ? (
        <WorkspacesSkeleton />
      ) : isError ? (
        <ErrorState error={error as ApiError} onRetry={() => void refetch()} />
      ) : (() => {
        const list = toList(data ?? {});
        if (list.length === 0) return <WorkspacesEmpty />;
        return (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((ws) => (
              <WorkspaceCard key={ws.name} ws={ws} />
            ))}
          </div>
        );
      })()}
    </section>
  );
}

// --- Usuários & Papéis (STUB — future, clearly labelled) ------------------

// TODO: auth real — these rows are DEMONSTRATION ONLY. There is no users/roles
// endpoint; RBAC is activated with real authentication. Do not treat as data.
const MOCK_USERS: { name: string; email: string; role: "Admin" | "User" }[] = [
  { name: "Claudio (gerente)", email: "claudio.gerente@exemplo", role: "Admin" },
  { name: "Agente — Zero", email: "zero@agente.local", role: "User" },
];

function RoleBadge({ role }: { role: "Admin" | "User" }) {
  const cls =
    role === "Admin"
      ? "bg-primary/15 text-primary"
      : "bg-surface-container-high text-on-surface-variant";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${cls}`}>
      {role}
    </span>
  );
}

function UsersSection() {
  return (
    <section className="rounded-2xl bg-surface-container/40 p-5">
      <SectionHeader
        icon="admin_panel_settings"
        title="Usuários e papéis"
        subtitle="Controle de acesso (RBAC) por usuário e papel."
        badge={<SoonBadge />}
      />

      {/* Visible honesty banner — this whole section is NOT real yet. */}
      <div className="mb-4 flex items-start gap-3 rounded-xl border border-primary-container/30 bg-primary-container/10 p-4">
        <span
          className="material-symbol mt-0.5 text-[20px] text-primary-container"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          info
        </span>
        <p className="text-body-sm text-on-surface">
          A gestão de usuários e papéis (RBAC) será ativada com a{" "}
          <strong>autenticação real</strong>. Hoje não existe endpoint de usuários no backend — a
          tabela abaixo é apenas uma <strong>demonstração</strong> da interface futura.
        </p>
      </div>

      {/* Demonstration table — explicitly labelled as mock, non-interactive. */}
      <div
        className="overflow-hidden rounded-xl border border-surface-border opacity-80"
        aria-label="Demonstração (dados fictícios)"
      >
        <div className="flex items-center gap-2 border-b border-surface-border bg-surface-container-high px-4 py-2">
          <span className="material-symbol text-[16px] text-content-subtle">visibility</span>
          <span className="text-label-sm font-semibold uppercase tracking-wide text-on-surface-variant">
            Demonstração — dados fictícios
          </span>
        </div>
        <table className="w-full text-left text-body-sm">
          <thead>
            <tr className="border-b border-surface-border text-on-surface-variant">
              <th className="px-4 py-2 font-semibold">Usuário</th>
              <th className="px-4 py-2 font-semibold">E-mail</th>
              <th className="px-4 py-2 font-semibold">Papel</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_USERS.map((u) => (
              <tr key={u.email} className="border-b border-surface-border/60 last:border-0">
                <td className="px-4 py-2.5 text-on-surface">{u.name}</td>
                <td className="px-4 py-2.5 text-on-surface-variant">{u.email}</td>
                <td className="px-4 py-2.5">
                  <RoleBadge role={u.role} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        disabled
        className="mt-4 inline-flex cursor-not-allowed items-center gap-1.5 rounded-xl bg-surface-container-high px-4 py-2 text-label-md font-semibold text-on-surface-variant opacity-60"
        aria-disabled="true"
        title="Disponível com a autenticação real"
      >
        <span className="material-symbol text-[18px]">person_add</span>
        Convidar usuário (em breve)
      </button>
    </section>
  );
}

// --- Page -----------------------------------------------------------------

export default function Admin() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-headline-md text-on-surface">Administração</h1>
        <p className="text-body-md text-on-surface-variant">
          Workspaces do projeto e controle de acesso (RBAC).
        </p>
      </header>

      <WorkspacesSection />
      <UsersSection />
    </div>
  );
}
