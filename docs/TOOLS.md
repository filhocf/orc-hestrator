# Tools reference

Generated from tools/list. Do not edit by hand: counts and names come
from the server (`tools/list`, `prompts/list`, `resources/list`).

Tools: **31** · Prompts: **7** · Resources: **6**

## Tools

| Tool | Description |
|---|---|
| `orc_onboarding` | Orc onboarding guide for this client type (read-only, no database).

client_type: hermes, kiro or cli (unknown values fall back to the
'generic' variant). lang: 'en' (canonical) or 'pt-BR'; empty resolves
via env ORC_LANG, then the Accept-Language header (HTTP transport),
then 'en'. Unknown languages fall back to 'en' without error.
 |
| `manage_items` | Create, update, or delete work items. Supports batch operations.

Operations: create, update, delete.
Priority: critical, high, medium, low. Complexity: 1-10.
Items support hierarchy via parent_id (max 4 levels deep).
Update: parent_id can be changed (reparenting). Set to "none" to unparent.
Batch create: pass items_json as JSON array of item objects.
Batch delete: pass ids_json as JSON array of item IDs. Use recursive=true to delete descendants.
due_at: optional ISO 8601 datetime string for due date (e.g. '2025-12-31T23:59:59+00:00').
 |
| `query_items` | Query work items. Operations: get (by id), list (with filters), children (of parent), overview (status counts).

Filters: status (queue/work/review/done/blocked/cancelled), priority, parent_id, search text, tags (comma-separated).
Use include_ancestors=true with get to see the full parent chain.
fields: projeta só as colunas pedidas (id,title,status,priority,parent_id,due_at,created_at…).
Campo inexistente devolve erro estruturado com field=fields, nunca silêncio.
compact=true (list): itens só com os campos de decisão (≤150 chars cada) e a página explícita
— {items, count, has_more, next_offset}. Sem compact, a resposta é a lista completa de hoje.
 |
| `advance_item` | Advance work items through workflow using triggers. Supports batch transitions.

Triggers: start (next phase), complete (jump to done), block/hold (pause), resume (unblock),
cancel (close), reopen (done/cancelled → queue).
Flow: queue → work → review → done. Checks dependency satisfaction and note gates.
Batch: pass transitions_json as JSON array of {item_id, trigger} objects.
Reopen cascades parent from terminal to work.
 |
| `get_next_status` | Read-only preview of what would happen with a given trigger.

Returns can_advance (bool), current status, next status, and any blockers.
Use before advance_item to check feasibility without side effects.
 |
| `get_next_item` | Get the highest-priority actionable item with no unsatisfied dependencies.

Returns the single best next item to work on, or null if nothing is actionable.
Priority: items already in 'work' first, then by priority (critical > high > medium > low).
Use workspace to filter by workspace tags (e.g. workspace="dtp").

compact: return only id (8 chars), title (≤60), status, priority, due_at and
`reason` — why this item won the queue ("in progress" / "overdue" /
"priority:<level>"). Use it on every turn; ask for the full item only when
you are about to work on it.
 |
| `get_context` | Get context snapshot for session resume or item inspection.

Without item_id: global dashboard — status counts, active items, blocked items, next action.
With item_id: item detail — children, notes, blockers, can_advance flag.
Use include_ancestors=true to get the full parent chain.
Use workspace to filter by workspace tags (e.g. workspace="dtp").
Use include_archived=true to include archived items in counts (excluded by default).
verbosity: "full" (default, whole rows — humano e depuração), "standard" (compacto +
description ≤200 chars) or "compact" (counts, next_item, active/blocked/stale como
[id,title,status,priority,stale_days], stale limitado a 10 com stale_total).
verbosity só se aplica ao dashboard global: com item_id o detalhe é sempre completo.
Call this at session start to understand current work state.
 |
| `get_execution_stack` | Get current execution stack showing active and suspended work frames.

Returns frames ordered by depth: deepest = most recent lateral.
Each frame shows item title, status, and saved execution-state if available.
Use to understand 'where am I' after interruptions.
 |
| `get_blocked_items` | Get all blocked items — both explicitly blocked and those with unsatisfied dependencies.

Use to identify what's stuck and what needs to be resolved to unblock progress.
fields: projeta só as colunas pedidas; compact=true devolve os campos de decisão
(≤150 chars por item). Sem os parâmetros, o payload é o de sempre.
 |
| `manage_notes` | Manage notes on work items. Notes are persistent documentation per phase.

Operations: upsert (create/update by key), delete, list (all notes for item).
Role: queue, work, review — indicates which phase the note belongs to.
Use notes to capture requirements, decisions, done-criteria, and handoff context.
 |
| `query_notes` | Query notes for a work item. Use include_body=false for token-efficient metadata checks.

With key: get a single note. Without key: list all notes for the item.
 |
| `manage_dependencies` | Manage dependency edges between work items.

Operations: add (from_id blocks to_id), remove, query (get deps for item_id), pattern.
Direction for query: inbound, outbound, both.
Pattern operation: create deps using shortcuts — linear, fan-out, fan-in.
  item_ids: comma-separated list of item IDs for pattern creation.
unblock_at: status threshold at which blocker unblocks (done, review, work). Default: done.
Dependencies enforce ordering — blocked items cannot advance until blockers reach unblock_at.
 |
| `query_dependencies` | Query dependencies with optional BFS traversal.

neighbors_only=true: direct edges only (fast). false: full BFS graph traversal.
Direction: outbound (what this blocks), inbound (what blocks this).
 |
| `create_work_tree` | Atomically create a root item + children + dependencies in one call.

children_json: JSON array of {ref, title, description, priority} objects.
deps_json: JSON array of {from, to, type?, unblock_at?} objects using ref names.
create_notes: auto-create blank notes from matching schemas (default: false).
Example: children=[{"ref":"a","title":"Schema"},{"ref":"b","title":"API"}], deps=[{"from":"a","to":"b"}]
 |
| `complete_tree` | Batch-complete all descendants of a parent item in topological order.

Skips items already in terminal status. Reports items that couldn't be completed (e.g., blocked by deps).
 |
| `manage_schemas` | View note schemas and check gate status for items.

Operations:
- list: show all loaded schemas
- get: show a specific schema by name
- check: check gate status for an item (requires item_id)
- reload: reload schemas from config file
 |
| `get_metrics` | Work metrics — throughput per week, average lead time, WIP count, stale ratio, breakdowns by priority and tag.

Optional days param controls the lookback period (default: 30).
Use workspace to filter by workspace tags (e.g. workspace="dtp").
 |
| `get_project_graph_metrics` | Compute project graph metrics — critical path, impact scores, bottlenecks.

Use to understand project topology: what's on the critical path,
what unblocks the most work, and whether current work is on-track.
 |
| `manage_archive` | Auto-archive completed items. Moves 'done' items older than archive_after_days to 'archived'.

Operations:
- run: archive eligible items (done status, older than archive_after_days)
- stats: return count of archived items and eligible items
- list: return all archived items (with optional workspace filter)
 |
| `export_graph` | Export the entire work graph (items, notes, dependencies) as JSON.

Returns a JSON object with items, notes, dependencies, exported_at timestamp, and version.
Use import_graph to restore from this export.
workspace: filter items by workspace name (uses workspace tag config).
tags: comma-separated tag list to filter items (ignored if workspace is set).
No params = export all (backward compatible).
 |
| `import_graph` | Import a work graph from JSON. Supports merge and replace modes.

data_json: JSON string from export_graph output.
mode: 'merge' inserts items/notes/deps that don't exist (skip on conflict).
      'replace' deletes everything first then inserts all.
 |
| `manage_checkpoints` | Manage checkpoint snapshots for backup and multi-machine sync.

Operations: create, list, restore, verify.
create: export current graph to a timestamped JSON file. Optional output_dir.
list: list available checkpoint files. Optional output_dir.
restore: restore graph from a checkpoint file (requires path).
verify: run PRAGMA integrity_check on the database.
 |
| `get_workspace_context` | Get workspace context at varying verbosity levels.

verbosity: minimal (counts + next), standard (+ active/blocked), full (+ recent decisions).
Returns workspace brief, status counts, memory_tags, next_item, and more based on verbosity.
 |
| `manage_workspaces` | Manage workspace configurations. Workspaces map tag groups for scoped queries.

Operations: create, update, delete, list.
tags: comma-separated list of item tags that belong to this workspace.
memory_tags: comma-separated list of memory service tags for this workspace.
description: brief description of the workspace purpose.
repos: comma-separated list of repository paths.
conventions: comma-separated list of coding conventions.
Use workspace param in get_context, get_next_item, get_metrics to filter by workspace.
 |
| `agent_register` | Register this agent session (central, cross-machine). Returns session_id — REUSE it.

Identity is the triple (hostname, agent_id, session_id). agent_id comes from X-Agent-ID;
hostname from arg → X-Client-Hostname header → 'unknown'; session_id is generated and
returned. Call agent_heartbeat(session_id) every 2-3 min and agent_end(session_id) on exit.
 |
| `agent_heartbeat` | Keep this session alive (call every 2-3 min). Sessions stale > 300s are reaped centrally. |
| `agent_end` | End this session and release all its claims (CASCADE). |
| `agent_list` | List active agent sessions across ALL machines. Optional filters by hostname or agent_id
(query by any level of the triple). Lazily reaps stale sessions first. Each row shows the
triple (hostname/agent_id/session_id) plus a human-readable label. |
| `claim` | Claim a work_item (validated against work_items.id) or a free-form resource (file/branch).

session_id (from agent_register) identifies the owning process. Conflict = another session_id
holds the same subject (even same persona+host) → CONFLICT naming the holder's triple.
subject_type: 'work_item' | 'resource'.
 |
| `release` | Release a previously claimed work_item/resource held by this session. |
| `conflicts` | Which of the given subjects are claimed by ANOTHER session (not expired).

subjects_json: JSON array of [subject_type, subject_ref] pairs or {type, ref} objects.
Returns the holder's triple (host/agent/session) for each conflict.
 |

## Prompts

| Prompt | Description |
|---|---|
| `work_summary` | Insight-driven dashboard: active work, blockers, and next actions.

Call get_context() and present a compact status report:
- Status counts (queue/work/review/done/blocked)
- Active items with progress
- Blocked items with reasons
- Next recommended action
 |
| `create_item_from_context` | Create a tracked work item from the current conversation context.

Analyze what the user is working on and create appropriate work items.
 |
| `quick_start` | Interactive onboarding — teaches by doing, adapts to empty or populated workspaces. |
| `status_progression` | Navigate role transitions; shows gate status and the correct trigger. |
| `dependency_manager` | Visualize, create, and diagnose dependencies between work items. |
| `batch_complete` | Complete or cancel multiple items at once — close out features or workstreams. |
| `session_start` | Load current work context at the beginning of each session. |

## Resources

| URI | Description |
|---|---|
| `orc://onboarding` | Orc onboarding — variant: hermes. Serves the language resolved per R9 (env ORC_LANG, then Accept-Language on HTTP; default en). Same text as the orc_onboarding tool. |
| `orc://onboarding/pt-br` | Orc onboarding em pt-BR (variant: hermes). |
| `orc://workflow` | Orc workflow. Serves the language resolved per R9 (env ORC_LANG, then Accept-Language on HTTP; default en). |
| `orc://workflow/pt-br` | Orc workflow em pt-BR: ciclo de vida, triggers, ciclo de sessão, gates. |
| `orc://glossary` | Orc glossary. Serves the language resolved per R9 (env ORC_LANG, then Accept-Language on HTTP; default en). |
| `orc://glossary/pt-br` | Orc glossário em pt-BR: termos-chave em prosa. |
