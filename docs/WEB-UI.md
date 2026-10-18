# Web interfaces

Two web surfaces exist. They are not alternatives chosen at runtime; they are different things
with different owners.

| | Management UI (`frontend/`) | Lightweight board (`src/task_orchestrator/ui/`) |
|---|---|---|
| Stack | React 18 + Vite + TypeScript + Tailwind | Jinja2 + HTMX + Tailwind, server-rendered |
| Served at | `/ui/` (build with `--base=/ui/`) | `/board`, `/timeline`, `/arcs` with `MCP_UI_ENABLED=1` |
| Screens | Nine: login, overview, live team, kanban, arcs, graph, task detail, users/RBAC, profile | Kanban with swimlanes, timeline, arc graph |
| Auth | Real user sessions with RBAC | None: inherits whatever the reverse proxy enforces |
| State source | REST API (`/api`) | The SQLite database directly |
| Intended use | The product's management surface | Zero-build local board for a single operator |

## Management UI

```bash
cd frontend && npm ci && npm run build      # emits dist/
# serve dist/ under /ui/ and proxy /api/ to the backend
```

In development the Vite server proxies `/api` to the backend on port 8005.

The React app is deliberately isolated from the Python tree: own lockfile, own CI job, own E2E suite
in `frontend/e2e/` (YAML scenarios driven by `run-ci.cjs`). A Python change that does not touch the
API contract must not require rebuilding the frontend.

## Lightweight board

```bash
ORC_DB=~/.local/share/orc/tasks.db uv run orc-ui --port 8080
```

Routes: `/board/{workspace}`, `/board/{workspace}/column/{status}`, `POST /board/move`,
`/timeline/{workspace}`, `/arcs`, `/arcs/{item_id}`, `/arcs/{item_id}/children`, `/item/{item_id}`.

The board is HTMX with partial updates. The arc graph is Cytoscape.js with a dagre layout loaded
from CDN, so the surface needs no build step and no Node toolchain. Nodes are coloured by status and
the root node carries a heavier border; clicking a node opens the item detail modal.

Known rough edges, unchanged for now: the database path is not auto-discovered (the env var is
required), the board has no visual error feedback, and the timeline is unstyled HTML.

## Which one is legacy

Neither is retired. Product work goes to the React UI; the server-rendered board stays because it
runs with no Node and no build, which is useful on a small host and for smoke-testing the engine
views. Removing it is a deliberate slice with an ADR, never a side effect of a refactor.
