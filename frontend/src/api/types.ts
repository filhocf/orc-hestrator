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
export interface Session {
  id: string;
  agent_id: string | null;
  hostname: string;
  pid: number;
  cli: string;
  theme: string;
  status: string;
  started_at: string;
  heartbeat_at: string;
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

// get_context() / get_workspace_context() — shape is workspace-view driven.
export interface Context {
  workspace: string | null;
  items?: WorkItem[];
  next_item?: WorkItem | null;
  counts?: Record<string, number>;
  [key: string]: unknown;
}

// get_metrics(days, workspace).
export interface Metrics {
  days: number;
  workspace: string | null;
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
