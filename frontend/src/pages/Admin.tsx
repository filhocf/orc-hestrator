import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createUser, getUsers, getWorkspaces } from "@/api/client";
import { ApiError } from "@/api/client";
import type { User, Workspace, WorkspacesMap } from "@/api/types";

/**
 * Administração / RBAC — screen 8.
 * Ported from the Stitch mockup intent:
 *   docs/design/stitch/administra_o_rbac_orc_hestrator/code.html
 *
 * Both sections are now REAL:
 *
 *   1. WORKSPACES (REAL): GET /api/workspaces. The backend returns a MAP keyed
 *      by workspace name (workspace.list_workspaces()), `{}` when none exist.
 *      We list name + description + tags + repos. Empty => a clear
 *      "Nenhum workspace configurado" state.
 *
 *   2. USUÁRIOS & PAPÉIS (REAL — F3): admin-only user management.
 *      GET /api/users -> { users: User[] } lists real users (username, role
 *      badge, active, created_at, last_login_at). A "Criar usuário" form POSTs
 *      to /api/users { username, password, role } and on success invalidates
 *      the list, clears the form and shows a success message. Errors are mapped
 *      to pt-BR (409 -> já existe, 400 -> dados inválidos, 403 -> sem permissão).
 *      The whole screen is admin-gated (sidebar hides it for non-admins and the
 *      backend returns 403 regardless).
 */

// --- Loading / error primitives (same visual language as Overview) --------

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-container-high/60 ${className}`} />;
}

function ErrorState({
  error,
  onRetry,
  title = "Não foi possível carregar os workspaces",
}: {
  error: ApiError | Error;
  onRetry: () => void;
  title?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl bg-surface-container-low p-8 text-center shadow-sm">
      <span className="material-symbol text-[40px] text-status-blocked">error</span>
      <div className="flex flex-col gap-1">
        <h2 className="font-display text-headline-sm text-on-surface">{title}</h2>
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

// --- Usuários & Papéis (REAL — F3) ----------------------------------------

/** Role pill for the real user list (admin | user). */
function RoleBadge({ role }: { role: string }) {
  const isAdmin = role === "admin";
  const cls = isAdmin
    ? "bg-primary/15 text-primary"
    : "bg-surface-container-high text-on-surface-variant";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${cls}`}>
      {isAdmin ? "admin" : "user"}
    </span>
  );
}

/** Active/inactive pill. */
function ActiveBadge({ active }: { active: boolean }) {
  const cls = active
    ? "bg-status-done/15 text-status-done"
    : "bg-surface-container-high text-on-surface-variant";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${cls}`}>
      {active ? "Ativo" : "Inativo"}
    </span>
  );
}

/** Format an ISO timestamp to pt-BR, or an em dash when null/unparseable. */
function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Map an ApiError from POST /api/users to a pt-BR message. */
function createUserErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) return "Usuário já existe.";
    if (err.status === 400) return "Dados inválidos.";
    if (err.status === 403) return "Sem permissão.";
  }
  return "Não foi possível criar o usuário. Tente novamente.";
}

function UsersTableSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

function UsersEmpty() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-surface-border bg-surface-container-low/50 p-10 text-center">
      <span className="material-symbol text-[40px] text-content-subtle">group_off</span>
      <h3 className="font-display text-title-md text-on-surface">Nenhum usuário cadastrado</h3>
      <p className="max-w-md text-body-sm text-on-surface-variant">
        Use o formulário abaixo para criar o primeiro usuário.
      </p>
    </div>
  );
}

function UsersList({ users }: { users: User[] }) {
  if (users.length === 0) return <UsersEmpty />;
  return (
    <div className="overflow-hidden rounded-xl border border-surface-border">
      <table className="w-full text-left text-body-sm">
        <thead>
          <tr className="border-b border-surface-border bg-surface-container-high text-on-surface-variant">
            <th className="px-4 py-2 font-semibold">Usuário</th>
            <th className="px-4 py-2 font-semibold">Papel</th>
            <th className="px-4 py-2 font-semibold">Status</th>
            <th className="px-4 py-2 font-semibold">Criado em</th>
            <th className="px-4 py-2 font-semibold">Último login</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b border-surface-border/60 last:border-0">
              <td className="px-4 py-2.5 font-medium text-on-surface">{u.username}</td>
              <td className="px-4 py-2.5">
                <RoleBadge role={u.role} />
              </td>
              <td className="px-4 py-2.5">
                <ActiveBadge active={u.active} />
              </td>
              <td className="px-4 py-2.5 text-on-surface-variant">{formatDateTime(u.created_at)}</td>
              <td className="px-4 py-2.5 text-on-surface-variant">
                {formatDateTime(u.last_login_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Create-user form. On success: invalidate the list, clear fields, show msg. */
function CreateUserForm() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "user">("user");
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const mutation = useMutation({
    mutationFn: () => createUser({ username: username.trim(), password, role }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      setUsername("");
      setPassword("");
      setRole("user");
      setErrorMsg("");
      setSuccessMsg(`Usuário "${res.user.username}" criado com sucesso.`);
    },
    onError: (err) => {
      setSuccessMsg("");
      setErrorMsg(createUserErrorMessage(err));
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!username.trim() || !password) {
      setSuccessMsg("");
      setErrorMsg("Preencha usuário e senha.");
      return;
    }
    setErrorMsg("");
    setSuccessMsg("");
    mutation.mutate();
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-5 flex flex-col gap-4 rounded-xl bg-surface-container-low p-4 shadow-sm"
      noValidate
    >
      <div className="flex items-center gap-2">
        <span className="material-symbol text-[20px] text-primary">person_add</span>
        <h3 className="font-display text-title-md text-on-surface">Criar usuário</h3>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-medium text-on-surface" htmlFor="new-username">
            Usuário
          </label>
          <input
            id="new-username"
            name="username"
            type="text"
            autoComplete="off"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="ex: maria.silva"
            className="w-full rounded-lg bg-surface-container-lowest px-3 py-2.5 text-[14px] text-on-surface shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-container/40"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-medium text-on-surface" htmlFor="new-password">
            Senha
          </label>
          <input
            id="new-password"
            name="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full rounded-lg bg-surface-container-lowest px-3 py-2.5 text-[14px] text-on-surface shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-container/40"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-medium text-on-surface" htmlFor="new-role">
            Papel
          </label>
          <select
            id="new-role"
            name="role"
            value={role}
            onChange={(e) => setRole(e.target.value as "admin" | "user")}
            className="w-full rounded-lg bg-surface-container-lowest px-3 py-2.5 text-[14px] text-on-surface shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-container/40"
          >
            <option value="user">user</option>
            <option value="admin">admin</option>
          </select>
        </div>
      </div>

      {errorMsg && (
        <p role="alert" className="text-[12px] font-medium text-status-blocked">
          {errorMsg}
        </p>
      )}
      {successMsg && (
        <p role="status" className="text-[12px] font-medium text-status-done">
          {successMsg}
        </p>
      )}

      <div>
        <button
          type="submit"
          disabled={mutation.isPending}
          className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-label-md font-semibold text-primary-contrast transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="material-symbol text-[18px]">person_add</span>
          {mutation.isPending ? "Criando..." : "Criar usuário"}
        </button>
      </div>
    </form>
  );
}

function UsersSection() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["users"],
    queryFn: () => getUsers(),
  });

  return (
    <section className="rounded-2xl bg-surface-container/40 p-5">
      <SectionHeader
        icon="admin_panel_settings"
        title="Usuários e papéis"
        subtitle="Controle de acesso (RBAC) por usuário e papel (GET /api/users)."
      />

      {isLoading ? (
        <UsersTableSkeleton />
      ) : isError ? (
        <ErrorState
          error={error as ApiError}
          onRetry={() => void refetch()}
          title="Não foi possível carregar os usuários"
        />
      ) : (
        <UsersList users={data?.users ?? []} />
      )}

      <CreateUserForm />
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
