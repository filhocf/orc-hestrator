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

export interface Workspace {
  name: string;
  count?: number;
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

// Cytoscape-style graph payload (ui/app.py arc_children_json).
export interface GraphNode {
  data: { id: string; label: string; status?: string };
}
export interface GraphEdge {
  data: { source: string; target: string };
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
