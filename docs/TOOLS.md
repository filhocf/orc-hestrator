# Tools reference

Generated from `tools/list`, `prompts/list` and `resources/list` on the server.
Do not edit by hand: a count that disagrees with the server is a bug in this file.

Tools: **31** · Prompts: **7** · Resources: **3**

## Tools

| Tool | Description |
|---|---|
| `advance_item` | Advance work items through workflow using triggers. Supports batch transitions. |
| `agent_end` | End this session and release all its claims (CASCADE). |
| `agent_heartbeat` | Keep this session alive (call every 2-3 min). Sessions stale > 300s are reaped centrally. |
| `agent_list` | List active agent sessions across ALL machines. Optional filters by hostname or agent_id |
| `agent_register` | Register this agent session (central, cross-machine). Returns session_id — REUSE it. |
| `claim` | Claim a work_item (validated against work_items.id) or a free-form resource (file/branch). |
| `complete_tree` | Batch-complete all descendants of a parent item in topological order. |
| `conflicts` | Which of the given subjects are claimed by ANOTHER session (not expired). |
| `create_work_tree` | Atomically create a root item + children + dependencies in one call. |
| `export_graph` | Export the entire work graph (items, notes, dependencies) as JSON. |
| `get_blocked_items` | Get all blocked items — both explicitly blocked and those with unsatisfied dependencies. |
| `get_context` | Get context snapshot for session resume or item inspection. |
| `get_execution_stack` | Get current execution stack showing active and suspended work frames. |
| `get_metrics` | Work metrics — throughput per week, average lead time, WIP count, stale ratio, breakdowns by priority and tag. |
| `get_next_item` | Get the highest-priority actionable item with no unsatisfied dependencies. |
| `get_next_status` | Read-only preview of what would happen with a given trigger. |
| `get_project_graph_metrics` | Compute project graph metrics — critical path, impact scores, bottlenecks. |
| `get_workspace_context` | Get workspace context at varying verbosity levels. |
| `import_graph` | Import a work graph from JSON. Supports merge and replace modes. |
| `manage_archive` | Auto-archive completed items. Moves 'done' items older than archive_after_days to 'archived'. |
| `manage_checkpoints` | Manage checkpoint snapshots for backup and multi-machine sync. |
| `manage_dependencies` | Manage dependency edges between work items. |
| `manage_items` | Create, update, or delete work items. Supports batch operations. |
| `manage_notes` | Manage notes on work items. Notes are persistent documentation per phase. |
| `manage_schemas` | View note schemas and check gate status for items. |
| `manage_workspaces` | Manage workspace configurations. Workspaces map tag groups for scoped queries. |
| `orc_onboarding` | Guia de onboarding do Orc em PT-BR, por tipo de cliente. |
| `query_dependencies` | Query dependencies with optional BFS traversal. |
| `query_items` | Query work items. Operations: get (by id), list (with filters), children (of parent), overview (status counts). |
| `query_notes` | Query notes for a work item. Use include_body=false for token-efficient metadata checks. |
| `release` | Release a previously claimed work_item/resource held by this session. |

## Prompts

| Prompt | Description |
|---|---|
| `batch_complete` | Complete or cancel multiple items at once — close out features or workstreams. |
| `create_item_from_context` | Create a tracked work item from the current conversation context. |
| `dependency_manager` | Visualize, create, and diagnose dependencies between work items. |
| `quick_start` | Interactive onboarding — teaches by doing, adapts to empty or populated workspaces. |
| `session_start` | Load current work context at the beginning of each session. |
| `status_progression` | Navigate role transitions; shows gate status and the correct trigger. |
| `work_summary` | Insight-driven dashboard: active work, blockers, and next actions. |

## Resources

| URI | Description |
|---|---|
| `orc://glossary` | Glossário de termos do Orc. |
| `orc://onboarding` | Onboarding completo do Orc (mesmo texto da tool orc_onboarding). |
| `orc://workflow` | Fluxo de trabalho: ciclo de vida, triggers e gates. |
