// Typed HTTP client for the Orchestrator REST API.
//
// Dev: the Vite dev server proxies "/api" to the Orc backend (see vite.config.ts).
// Override the base at build/runtime with VITE_API_BASE (e.g. "https://cfnarede.dev/orc").
import type {
  AdvanceTrigger,
  ArcChildren,
  ArcsPage,
  Claim,
  Context,
  Graph,
  ItemsPage,
  Metrics,
  Session,
  ToolErrorBody,
  WorkItem,
  Workspace,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
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

export function getWorkspaces(): Promise<Workspace[]> {
  return request<Workspace[]>(`/workspaces`);
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
