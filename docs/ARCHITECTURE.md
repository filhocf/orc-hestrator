# Architecture

Orc[hestrator] is a thin MCP layer over a modular domain engine, backed by SQLite, with an
optional web layer. This document describes the current system; decisions and their rationale
live in `docs/adr/`.

## Layers

```
  MCP clients (agents)          Browser (human)
        │                              │
        ▼                              ▼
  server.py  (FastMCP tools)     web/api.py (REST, auth)     frontend/ (React SPA)
        └──────────────┬───────────────┴───────────────────────────┘
                       ▼
                 engine/ (domain)
                       │
                       ▼
              db.py — SQLite (WAL) + FTS5
```

Every entry point is a thin adapter. Business rules live in `engine/` and are enforced there, so
a client cannot bypass the state machine by calling the REST API instead of MCP.

## Source layout

```
src/task_orchestrator/
├── server.py        MCP tools (FastMCP), agent identity resolution, HTTP health
├── onboarding.py    self-teaching surface: orc_onboarding tool and static resources
├── prompts.py       MCP workflow prompts registered on the server
├── engine/          domain logic, one module per concern
│   ├── base          errors, constants, short-id resolution
│   ├── items         work item CRUD, hierarchy, FTS search
│   ├── transitions   state machine, gates, unblocking
│   ├── dependencies  graph, cycle detection, BFS
│   ├── notes         per-phase notes and schema gates
│   ├── queries       read views: next item, blocked, context, scheduling
│   ├── trees         atomic work-tree creation and completion
│   ├── metrics       throughput, lead time, critical path, impact
│   ├── archive       auto-archive of completed items
│   ├── portability   export / import
│   ├── workspace_view  workspace context, execution stack
│   ├── presence      sessions: hostname/agent/session triple, heartbeat, reaping
│   ├── claims        work items and free-form resources, conflict detection
│   └── users         accounts, roles, sessions for the web layer
├── db.py            schema, additive migrations, FTS5
├── schemas.py       note-gate schema definitions
├── workspace.py     workspace configuration
├── web/             REST API over the engine, graph endpoints
└── ui/              optional server-rendered board (FastAPI + HTMX)
frontend/            React management UI, isolated from the Python tree
```

Modules form a strict import DAG: `base` is a leaf, feature modules depend only on it and on the
database helper, and `engine/__init__.py` re-exports the public surface so clients keep a stable
`engine.X` interface. That facade is why the 1.3.0 split of a ~1,960-line `engine.py` into modules
shipped without a public API change.

## Work model

An item is a node with a status, a parent (up to four levels), and edges:

- **Hierarchy** — parent/child, used for arcs and decomposition.
- **Dependencies** — directed edges with an `unblock_at` threshold, so a consumer can start when
  the producer reaches `review` instead of `done`. Cycles are rejected at creation time.
- **Notes** — keyed by phase. A YAML schema declares which notes a phase requires; the transition
  is refused while a required note is missing. That is what makes `done` mean something.

Statuses are `queue`, `work`, `review`, `done`, with `blocked` and `cancelled` as side states.
Transitions are trigger-driven (`start`, `complete`, `block`, `resume`, `cancel`, `reopen`) and
the engine rejects anything the state machine does not allow.

## Identity and coordination

Three identities compose: **hostname**, **agent_id**, **session_id**.

- `agent_id` is resolved per request, with precedence: explicit argument → `X-Agent-ID` header →
  `MCP_AGENT_ID` environment → OAuth client id → null. It is stored on writes as
  `created_by` / `updated_by` (ADR-005).
- A session registers, heartbeats every few minutes, and is reaped when stale. `agent_end`
  releases its claims in cascade.
- A claim answers "who is on this item" before two agents duplicate work. Claims cover work items
  (validated against the items table) and free-form resources such as files or branches.

## Storage

One SQLite file in WAL mode, with FTS5 for search. Migrations are additive and idempotent, applied
on startup. The engine is synchronous; the MCP and HTTP layers are async adapters around it.
Foreign keys are enforced, so deletes cascade where the model says they should.

Deployments run one central instance so that state has a single owner (ADR-001). A local file is a
single-machine convenience, not a sync strategy.

## Access control

Two audiences, two mechanisms:

- **Humans** authenticate to the web layer with a password (scrypt, per-user salt) and carry an
  opaque session token in an HTTP-only cookie, revocable server-side. Roles are `admin` and `user`.
  Every `/api/*` route except login, logout and `/health` requires a session.
- **Agents** authenticate to MCP through the reverse proxy's basic auth and, optionally, an OAuth2
  resource-server layer (`MCP_OAUTH_ENABLED`) that verifies opaque pre-shared tokens (ADR-004).

The initial admin is seeded on first boot from `ORC_ADMIN_USER` / `ORC_ADMIN_PASSWORD`.

## Deployment shape

An HTTP transport (`streamable-http`) serves three surfaces from one process: `/mcp` for agents,
`/api` for the SPA, and `/ui/` for the management UI. A reverse proxy terminates TLS and adds the
edge credential. The web extra is optional: without `fastapi` installed the MCP server still runs,
and `uv sync --extra ui` is required when the web surfaces are wanted.

## Testing

Three layers: engine tests against a temporary database, MCP surface tests through the real
FastMCP object, and end-to-end tests that spawn the server in a subprocess and speak MCP to it with
the official client. The React UI is covered by YAML-driven browser tests in `frontend/e2e/`. A
green test suite never closes a gate on its own: the acceptance number is measured against the real
execution path.
