// Typed HTTP client for the Orchestrator REST API.
//
// Dev: the Vite dev server proxies "/api" to the Orc backend (see vite.config.ts).
// Override the base at build/runtime with VITE_API_BASE (e.g. "https://cfnarede.dev/orc").
import type {
  AdvanceTrigger,
  ArcChildren,
  ArcsPage,
  AuthResponse,
  Claim,
  Context,
  Graph,
  ItemsPage,
  ItemDetail,
  Metrics,
  Session,
  ToolErrorBody,
  WorkItem,
  WorkspacesMap,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

/** Typed error thrown when the backend returns a structured ToolError body or a non-2xx status. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly field?: string;

  constructor(status: number, code: string, message: string, field?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

function isToolErrorBody(body: unknown): body is ToolErrorBody {
  return (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof (body as ToolErrorBody).error?.message === "string"
  );
}

/**
 * Global 401 handler. The AuthProvider registers a callback here so that any
 * request whose session has expired (HTTP 401) can drive a redirect to /login
 * from a single place, instead of every caller handling it. The login/me
 * endpoints themselves are exempt (a 401 there is an expected auth outcome,
 * not an expired session) — see {@link request}'s `skipAuthRedirect`.
 */
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

/** Register (or clear with null) the global handler fired on an unexpected 401. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

async function request<T>(
  path: string,
  init?: RequestInit & { skipAuthRedirect?: boolean },
): Promise<T> {
  const { skipAuthRedirect, ...rest } = init ?? {};
  const res = await fetch(`${API_BASE}${path}`, {
    // Send the HttpOnly orc_session cookie on every request; without this the
    // browser omits credentials for same-origin fetch defaults in some setups
    // and (critically) for any cross-origin VITE_API_BASE deployment.
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
    ...rest,
  });

  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    // Session expired mid-use: let the app redirect to /login. Skipped for the
    // auth endpoints, where a 401 is a normal "bad credentials / no session"
    // signal the caller handles directly.
    if (res.status === 401 && !skipAuthRedirect) {
      onUnauthorized?.();
    }
    if (isToolErrorBody(body)) {
      throw new ApiError(res.status, body.error.code, body.error.message, body.error.field);
    }
    throw new ApiError(res.status, "HTTP_ERROR", typeof body === "string" && body ? body : res.statusText);
  }

  return body as T;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  if (entries.length === 0) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of entries) sp.set(k, String(v));
  return `?${sp.toString()}`;
}

// --- Auth endpoints (F2) --------------------------------------------------

/**
 * Exchange credentials for a server session. On success the backend sets the
 * HttpOnly `orc_session` cookie (SameSite=Lax) and returns the user. A 401
 * ("bad credentials") is surfaced as an ApiError to the caller WITHOUT firing
 * the global unauthorized redirect (skipAuthRedirect).
 */
export function login(username: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>(`/auth/login`, {
    method: "POST",
    body: JSON.stringify({ username, password }),
    skipAuthRedirect: true,
  });
}

/** Clear the server session (backend expires the orc_session cookie). 204. */
export function logout(): Promise<void> {
  return request<void>(`/auth/logout`, {
    method: "POST",
    skipAuthRedirect: true,
  });
}

/**
 * Bootstrap the session from the cookie. 200 + { user } when the orc_session
 * cookie is valid; 401 when there is no session. A 401 here is expected (not
 * an expired session mid-use), so it does NOT trigger the global redirect.
 */
export function getMe(): Promise<AuthResponse> {
  return request<AuthResponse>(`/auth/me`, { skipAuthRedirect: true });
}

// --- Read endpoints -------------------------------------------------------

export function getContext(workspace?: string): Promise<Context> {
  return request<Context>(`/context${qs({ workspace })}`);
}

export function getItems(params: {
  status?: string;
  parent_id?: string;
  priority?: string;
  search?: string;
  tags?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<WorkItem[]> {
  return request<WorkItem[]>(`/items${qs(params)}`);
}

export function getItem(id: string): Promise<WorkItem> {
  return request<WorkItem>(`/items/${encodeURIComponent(id)}`);
}

/**
 * Full item detail. Same endpoint as {@link getItem} but typed with the extra
 * fields the backend attaches (children, notes, dependencies, claim). REAL
 * shape confirmed live (http://127.0.0.1:8005/api/items/<id>):
 *   WorkItem + { children: WorkItem[], notes: ItemNote[],
 *                dependencies: { blocks, blocked_by }, claim: ClaimOwner|null }.
 */
export function getItemDetail(id: string): Promise<ItemDetail> {
  return request<ItemDetail>(`/items/${encodeURIComponent(id)}`);
}

/**
 * Paginated list of work items. Unlike {@link getItems} (which assumed a bare
 * array), this mirrors the REAL backend envelope confirmed live:
 *   GET /api/items -> { items, total, limit, offset }
 */
export function getItemsPage(params: {
  status?: string;
  parent_id?: string;
  priority?: string;
  search?: string;
  tags?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<ItemsPage> {
  return request<ItemsPage>(`/items${qs(params)}`);
}

/**
 * Root arcs list. REAL envelope confirmed live:
 *   GET /api/arcs -> { items: WorkItem[], total, limit, offset }
 * (items = root arcs: parent_id null, tags include "arc").
 */
export function getArcs(params: { sort?: string } = {}): Promise<ArcsPage> {
  return request<ArcsPage>(`/arcs${qs(params)}`);
}

/**
 * Direct children of an arc/node. REAL envelope confirmed live:
 *   GET /api/arcs/{id} -> { children: WorkItem[] }
 */
export function getArcChildren(id: string): Promise<ArcChildren> {
  return request<ArcChildren>(`/arcs/${encodeURIComponent(id)}`);
}

export function getSessions(
  params: { hostname?: string; agent_id?: string } = {},
): Promise<Session[]> {
  return request<Session[]>(`/sessions${qs(params)}`);
}

export function getClaims(): Promise<Claim[]> {
  return request<Claim[]>(`/claims`);
}

export function getMetrics(params: { days?: number; workspace?: string } = {}): Promise<Metrics> {
  return request<Metrics>(`/metrics${qs(params)}`);
}

export function getGraph(arc: string): Promise<Graph> {
  return request<Graph>(`/graph/${encodeURIComponent(arc)}`);
}

/**
 * Workspace configuration map. REAL envelope confirmed live
 * (http://127.0.0.1:8005/api/workspaces -> {} today): a map keyed by workspace
 * name, each value = { tags, memory_tags, description, repos, conventions }.
 * NOT an array (an earlier type assumed Workspace[], which was wrong).
 */
export function getWorkspaces(): Promise<WorkspacesMap> {
  return request<WorkspacesMap>(`/workspaces`);
}

// --- Write endpoints ------------------------------------------------------

export function advanceItem(id: string, trigger: AdvanceTrigger, note?: string): Promise<WorkItem> {
  return request<WorkItem>(`/items/${encodeURIComponent(id)}/advance`, {
    method: "PATCH",
    body: JSON.stringify({ trigger, note }),
  });
}

export function claim(subjectRef: string, subjectType: "work_item" | "resource" = "work_item"): Promise<Claim> {
  return request<Claim>(`/claims`, {
    method: "POST",
    body: JSON.stringify({ subject_ref: subjectRef, subject_type: subjectType }),
  });
}

export function release(claimId: string): Promise<{ released: boolean }> {
  return request<{ released: boolean }>(`/claims/${encodeURIComponent(claimId)}`, {
    method: "DELETE",
  });
}
