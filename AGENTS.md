# AGENTS.md

## Project Overview

MCP server for work item management — tasks, dependencies, notes, workspaces, and workflow automation. Built with Python (FastMCP), SQLite storage, Streamable HTTP transport on port 3201. Entry point: `src/task_orchestrator/server.py`.

## Architecture

```
src/task_orchestrator/
├── server.py            ← FastMCP server, registers all MCP tools (thin layer over engine)
├── engine/              ← domain logic, split from the former monolithic engine.py
│   ├── __init__.py      ← facade: re-exports the public API as `engine.X` (back-compat)
│   ├── base.py          ← ToolError, constants (TRANSITIONS/TERMINAL/PRIORITIES), helpers (_now/_uid/_parse_dt/_row_to_dict), resolve_short_id, workspace tag filter
│   ├── items.py         ← WorkItem CRUD, hierarchy, basic queries, FTS search
│   ├── transitions.py   ← state machine (queue→work→review→done), gates, unblock logic
│   ├── dependencies.py  ← dependency graph, BFS traversal, cycle detection
│   ├── notes.py         ← per-phase notes (upsert/get/delete), auto-reopen
│   ├── queries.py       ← read views: get_next_item, get_blocked_items, get_context, scheduling
│   ├── trees.py         ← create_work_tree, complete_tree (aggregators)
│   ├── metrics.py       ← throughput, lead time, WIP, project graph metrics
│   ├── archive.py       ← auto-archive of done items
│   ├── portability.py   ← export_graph / import_graph
│   └── workspace_view.py← workspace context, execution stack
├── db.py                ← SQLite schema + additive migrations + FTS5 (WAL mode)
├── schemas.py           ← note-gate schemas, gate enforcement (check_gate)
├── workspace.py         ← workspace configs, scoped tag queries
├── checkpoints.py       ← checkpoint snapshots (export/import wrappers)
├── prompts.py           ← MCP prompts registration
└── ui/                  ← optional FastAPI + Kanban web UI (MCP_UI_ENABLED)
```

**Import rule:** `engine/` is a DAG — `base` ← leaf modules (items, transitions, dependencies, notes, archive, portability) ← aggregators (queries, metrics, workspace_view, trees). No module imports an aggregator back. External code (server.py, checkpoints.py, tests) uses `engine.X` via the facade — do not import submodules directly from outside the package.

**Data flow:** Tool call → validate params → engine function → DB operation → state transition (if applicable) → return result.

## Key Conventions

- **Storage**: single SQLite file (`~/.task-orchestrator/tasks.db`). WAL mode enabled.
- **State machine**: queue → work → review → done. Triggers: start, complete, block, hold, resume, cancel, reopen.
- **Dependencies**: `from_id` blocks `to_id`. Configurable `unblock_at` (done, review, work).
- **Reparenting**: Items can be reparented via update (parent_id field). Max depth: 4 levels. Set parent_id to "none" to unparent.
- **Workspaces**: tag-based filtering. Config in `workspaces.json`.
- **Transport**: `MCP_TRANSPORT=streamable-http` (default) or `stdio`. Port via `MCP_PORT` (default 3201).

## Adding a New Tool

1. Define the tool function in `server.py` with `@mcp.tool(name=..., description=...)`.
2. Use `Annotated[type, Field(description=...)]` for all parameters.
3. Call storage/workflow functions for business logic.
4. Add tests in `tests/`.

## Tests

```bash
pytest                    # All tests
pytest tests/test_api.py  # Specific module
```

- Tests use temp SQLite databases (auto-cleanup).
- No external dependencies needed for testing.
