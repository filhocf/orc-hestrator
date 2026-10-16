// API types for the Orchestrator Control Hub.
//
// These shapes are derived from the AUTHORITATIVE backend data model
// (src/task_orchestrator/db.py + engine/*.py), because the referenced
// docs/specs/SPEC-http-api.md did not exist on this branch at scaffold time.
// When the formal SPEC lands, reconcile these types against it.

export type ItemStatus =
  | "queue"
  | "work"
  | "review"
  | "done"
  | "blocked"
  | "cancelled"
  | "archived";

export type Priority = "critical" | "high" | "medium" | "low";

// advance() triggers (engine/base.py TRANSITIONS + resume/hold).
export type AdvanceTrigger =
  | "start"
  | "complete"
  | "block"
  | "cancel"
  | "reopen"
  | "archive"
  | "resume"
  | "hold";

// Mirrors the work_items table (db.py SCHEMA + MIGRATIONS, incl. created_by/updated_by).
export interface WorkItem {
  id: string;
  parent_id: string | null;
  title: string;
  description: string;
  summary: string;
  status: ItemStatus;
  status_label: string | null;
  previous_status: string | null;
  priority: Priority;
  complexity: number | null;
  item_type: string;
  tags: string;
  metadata: string | null;
  properties: string | null;
  role_changed_at: string | null;
  due_at: string | null;
  schedule: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
}

// Mirrors the sessions table (triple identity: agent_id + hostname + pid/cli).
// Shape confirmed against the live backend (GET http://127.0.0.1:8005/api/sessions):
//   { agent_id, hostname, pid, cli, theme, status, started_at, heartbeat_at,
//     session_id, label }
// NOTE: the live payload has NO top-level `id`; the identifier is `session_id`.
export interface Session {
  session_id: string;
  agent_id: string | null;
  hostname: string;
  pid: number;
  cli: string;
  theme: string;
  status: string;
  started_at: string;
  heartbeat_at: string;
  label: string;
}

// Mirrors the unified claims table (subject_type: work_item | resource).
export interface Claim {
  id: string;
  subject_type: "work_item" | "resource";
  subject_ref: string;
  session_id: string;
  agent_id: string | null;
  resource_type: string | null;
  claimed_at: string;
  expires_at: string | null;
}

export interface Dependency {
  id: string;
  from_id: string;
  to_id: string;
  dep_type: string;
  unblock_at: string;
  created_at: string;
}

// A single dependency edge as returned by GET /api/items/{id} inside the
// `dependencies` object. Confirmed live: the engine joins the related item's
// title/status onto the raw dependencies row, so an outbound ("blocks") edge
// carries to_title/to_status and an inbound ("blocked_by") edge carries
// from_title/from_status. All join columns are optional to stay honest about
// what each direction actually includes.
export interface DependencyEdge {
  id: string;
  from_id: string;
  to_id: string;
  dep_type: string;
  unblock_at: string;
  created_at: string;
  created_by?: string | null;
  to_title?: string;
  to_status?: ItemStatus | string;
  from_title?: string;
  from_status?: ItemStatus | string;
}

// GET /api/items/{id} -> `dependencies` object (engine.get_dependencies(id,"both")).
// Confirmed live: { blocks: DependencyEdge[], blocked_by: DependencyEdge[] }.
export interface ItemDependencies {
  blocks: DependencyEdge[];
  blocked_by: DependencyEdge[];
}

// A note attached to a work item (notes table: id,item_id,key,role,body,created_at,updated_at).
// Confirmed via engine.get_notes -> SELECT * FROM notes.
export interface ItemNote {
  id: string;
  item_id: string;
  key: string;
  role: string;
  body: string;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
}

// The active claim owner triple returned by GET /api/items/{id} `claim`
// (engine.get_claim_for -> _owner_triple), or null when unclaimed.
export interface ClaimOwner {
  session_id: string;
  agent_id: string | null;
  hostname: string;
  cli: string;
  label: string;
  claimed_at: string;
  expires_at: string | null;
  subject_type: string;
  subject_ref: string;
  resource_type: string | null;
}

// GET /api/items/{id} — the FULL item detail. Confirmed live
// (http://127.0.0.1:8005/api/items/<id>): a flattened WorkItem plus
// children[], notes[], dependencies{blocks,blocked_by}, claim|null.
export interface ItemDetail extends WorkItem {
  children: WorkItem[];
  notes: ItemNote[];
  dependencies: ItemDependencies;
  claim: ClaimOwner | null;
}

export interface Workspace {
  name: string;
  count?: number;
}

// GET /api/items — paginated list envelope.
// Shape confirmed against the live backend (http://127.0.0.1:8005/api/items):
//   { items: WorkItem[], total: number, limit: number, offset: number }
export interface ItemsPage {
  items: WorkItem[];
  total: number;
  limit: number;
  offset: number;
}

// GET /api/arcs — the root arcs list envelope.
// Shape confirmed against the live backend (http://127.0.0.1:8005/api/arcs):
//   { items: WorkItem[], total, limit, offset }  (items = root arcs, parent_id null, tag "arc")
export interface ArcsPage {
  items: WorkItem[];
  total: number;
  limit: number;
  offset: number;
}

// GET /api/arcs/{id} — direct children of an arc/node.
// Shape confirmed against the live backend (http://127.0.0.1:8005/api/arcs/<id>):
//   { children: WorkItem[] }
export interface ArcChildren {
  children: WorkItem[];
}

// Per-status counts returned by GET /api/context (keys present depend on data).
export interface ContextCounts {
  queue?: number;
  work?: number;
  review?: number;
  done?: number;
  blocked?: number;
  cancelled?: number;
  archived?: number;
  [status: string]: number | undefined;
}

// GET /api/context — the dashboard aggregate.
// Shape confirmed against the live backend (http://127.0.0.1:8005/api/context).
export interface Context {
  counts: ContextCounts;
  active: WorkItem[];
  blocked: WorkItem[];
  recent_completed: WorkItem[];
  next_item: WorkItem | null;
  stale_items: WorkItem[];
  due_soon: WorkItem[];
  overdue: WorkItem[];
  scheduled_upcoming?: WorkItem[];
  workspace?: string | null;
  [key: string]: unknown;
}

// Single bucket of the weekly throughput series.
export interface ThroughputBucket {
  week: string; // ISO week label, e.g. "2026-W42"
  count: number;
}

// GET /api/metrics — aggregate metrics.
// Shape confirmed against the live backend (http://127.0.0.1:8005/api/metrics).
export interface Metrics {
  throughput_per_week: ThroughputBucket[];
  lead_time_avg_seconds: number;
  wip: number;
  stale_ratio: number;
  by_priority: Record<string, number>;
  by_tag: Record<string, number>;
  total_items: number;
  period_days: number;
  [key: string]: unknown;
}

// Cytoscape-style graph payload.
// Shape confirmed live (http://127.0.0.1:8005/api/graph/<arc_id>):
//   { nodes: [{ data: { id, label, status, is_root } }],
//     edges: [{ data: { source, target } }] }
// NOTE: the live edge payload has NO `id` (the brief lists one as optional); it
// is typed optional and synthesized client-side when absent.
export interface GraphNode {
  data: { id: string; label: string; status?: ItemStatus | string; is_root?: boolean };
}
export interface GraphEdge {
  data: { id?: string; source: string; target: string };
}
export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Structured error returned by the backend (engine/base.py ToolError.to_dict()).
export interface ToolErrorBody {
  error: {
    code: "NOT_FOUND" | "VALIDATION" | "CONFLICT" | "DEPENDENCY_UNSATISFIED" | "GATE_BLOCKED" | string;
    message: string;
    field?: string;
  };
}
