# AGENTS.md

Instructions for agents working **in this repository**. For the product itself, read the
[README](README.md); for requirements, [docs/PRD.md](docs/PRD.md).

## Project overview

Orc[hestrator] — an MCP server that keeps work items, dependencies, gates, agent presence and
claims in one place, with an optional web UI. Python 3.11+, FastMCP, SQLite (WAL + FTS5).
Entry point: `src/task_orchestrator/server.py`.

Distribution name: `orc-hestrator` (formerly `task-orchestrator-py`). Commands: `orc`, `orc-ui`.
The Python import package stays `task_orchestrator` — see `docs/adr/ADR-006-rename-orc-hestrator.md`.

## Architecture

```
src/task_orchestrator/
├── server.py            ← FastMCP tools (thin layer), agent identity resolution, /health
├── onboarding.py        ← orc_onboarding tool + static resources (self-teaching surface)
├── prompts.py           ← MCP workflow prompts
├── engine/              ← domain logic, one module per concern
│   ├── __init__.py      ← facade: re-exports the public API as `engine.X` (back-compat)
│   ├── base.py          ← ToolError, constants, helpers, resolve_short_id
│   ├── items.py         ← WorkItem CRUD, hierarchy, FTS search
│   ├── transitions.py   ← state machine, gates, unblock logic
│   ├── dependencies.py  ← graph, BFS, cycle detection
│   ├── notes.py         ← per-phase notes, auto-reopen
│   ├── queries.py       ← next item, blocked, context, scheduling
│   ├── trees.py         ← create_work_tree, complete_tree
│   ├── metrics.py       ← throughput, lead time, critical path, impact
│   ├── archive.py       ← auto-archive of done items
│   ├── portability.py   ← export_graph / import_graph
│   ├── workspace_view.py← workspace context, execution stack
│   ├── presence.py      ← sessions (hostname/agent_id/session_id), heartbeat, reaping
│   ├── claims.py        ← work items and free-form resources, conflict detection
│   └── users.py         ← accounts, roles, web sessions
├── db.py                ← schema + additive migrations + FTS5
├── schemas.py           ← note-gate schemas and gate enforcement
├── workspace.py         ← workspace configs, scoped tag queries
├── checkpoints.py       ← checkpoint snapshots
├── web/                 ← REST API over the engine (/api), graph endpoints
└── ui/                  ← optional server-rendered board (FastAPI + HTMX)
frontend/                ← React management UI (Vite + TS + Tailwind), isolated from Python
```

**Import rule:** `engine/` is a DAG — `base` ← feature modules ← aggregators. No module imports an
aggregator back. External code (`server.py`, `web/`, `checkpoints.py`, tests) uses `engine.X` via
the facade; do not import submodules directly from outside the package.

**Data flow:** tool call → validate → engine function → DB → transition → structured result.

## Conventions that bite

- **Storage:** one SQLite file. `ORC_DB` (fallback `TASK_ORCHESTRATOR_DB`), default
  `~/.orc/tasks.db`. WAL mode.
- **Transport default is stdio.** `MCP_TRANSPORT=streamable-http` is what deployments use, not the
  default: `os.environ.get("MCP_TRANSPORT", "stdio")`. Port comes from `MCP_PORT` (default 3201;
  the reference deployment uses 8005 behind a proxy).
- **The web extra is optional.** `fastapi` lives in the `ui` extra: after any plain `uv sync` the
  streamable-http path dies with `ModuleNotFoundError: fastapi`. Always
  `uv sync --extra test --extra ui` in a dev environment.
- **State machine:** queue → work → review → done; triggers start, complete, block/hold, resume,
  cancel, reopen. The engine rejects anything else — never bypass it from an adapter.
- **Dependencies:** `from_id` blocks `to_id`, with `unblock_at` ∈ {done, review, work}. Max
  hierarchy depth is 4.
- **Identity:** `agent_id` resolves per request (argument → `X-Agent-ID` → `MCP_AGENT_ID` → OAuth
  client id) through a contextvar that must be reset. Never cache it across requests.
- **Two audiences, two auth paths:** humans use cookie sessions with RBAC on `/api/*`; agents use
  the proxy's basic auth and optionally OAuth2 (`MCP_OAUTH_ENABLED`).

## Adding a tool

1. Implement the domain rule in `engine/` first. The tool is an adapter.
2. Register in `server.py` with a docstring that states the operations and constraints; annotate
   `-> str` for consistency with the other tools.
3. Decorate with `@with_agent_id` if the tool writes state.
4. Add tests at three levels: engine, MCP surface, and a real client call when the contract is
   about the wire.
5. Regenerate `docs/TOOLS.md` — it is derived from the server, never hand-written.

## Tests

```bash
uv sync --extra test --extra ui
uv run pytest tests/ -q                # full suite
uv run pytest tests/test_engine.py -q  # one module
uv run ruff check . && uv run ruff format --check .
```

- Tests use temporary SQLite databases; never touch a real database.
- A green suite does not close a gate by itself: measure the acceptance criterion against the real
  execution path (spawn the server, speak MCP to it) before claiming done.
- `tests/test_onboarding.py` includes a subprocess test that boots the server on a free port; it
  must leave no `.db` artifact behind.

## Where things are decided

- `docs/adr/` — architecture decisions, one file per decision, immutable once accepted.
- `docs/specs/` — per-slice requirements with verifiable acceptance criteria.
- `docs/BRING-YOUR-AGENT.md` — how an agent connects and what it gets.
- `CHANGELOG.md` — what shipped and when. Product requirements are never tracked here.
