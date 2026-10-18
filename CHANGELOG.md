# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.1] - 2026-10-18

### Fixed
- **UI assets/routes under a base path.** Absolute references (`src="/mascote.png"`, router
  `basename`) ignored Vite's `base`, resolving to the domain root and 404-ing when the SPA is
  served under a subpath (e.g. `/orc/ui/`). Now use `import.meta.env.BASE_URL` for the mascot
  logo (`Layout`, `Login`, `Overview`) and the `BrowserRouter` basename, and the favicon points
  to `mascote.png` (the removed `.svg` left the icon broken).

### Deployment notes
- The web extra (`fastapi`) is **optional** (`[project.optional-dependencies] ui`). Deploys must
  run `uv sync --extra ui`; a plain `uv sync` omits `fastapi` and the service restart-loops with
  `ModuleNotFoundError: fastapi`.
- Serving the SPA under a subpath: build with `vite build --base=/orc/ui/ (VITE_API_BASE=/orc/api)`
  and reverse-proxy `/orc/api/` to the backend. The initial admin is seeded from
  `ORC_ADMIN_USER`/`ORC_ADMIN_PASSWORD` on first boot when no user exists.
- First production deploy of the management UI + real auth validated live at
  `https://cfnarede.dev/orc/ui/` (login, session cookie, RBAC, real dashboard data).

## [1.5.0] - 2026-10-16

### Added
- **Decoupled React management UI** (`frontend/`, Vite + React 18 + TypeScript + Tailwind):
  9 screens consuming the REST API — login, dashboard/overview, live team presence
  (host/agent/session triple), kanban board, arcs tree, DAG graph (Cytoscape), task detail,
  admin/RBAC, profile. Design from Stitch (`docs/design/stitch/`). Dark/light theme.
  E2E navigation tests via playwright-with-yaml (`frontend/e2e/`).
- **REST API over the engine** (`web/api.py`, mounted at `/api` on the streamable-http app):
  reads (items, items/{id}, arcs, context, sessions, claims, metrics, graph, workspaces) and
  writes (advance, claims). Thin layer reusing the engine — see `docs/specs/SPEC-http-api.md`.
- **User authentication + RBAC** (`engine/users.py`, `docs/specs/SPEC-user-auth-rbac.md`):
  `POST /api/auth/login|logout`, `GET /api/auth/me`; scrypt password hashing (stdlib, per-user
  salt, constant-time compare); opaque session token in an HTTP-only cookie with server-side
  revocation; roles `admin`/`user`; `require_admin` guard; `GET/POST /api/users` (admin-only,
  never leaks the hash); initial admin seeded from `ORC_ADMIN_USER`/`ORC_ADMIN_PASSWORD`.
  `get_current_user` now validates the session cookie (the SPEC-http-api R10 extension point),
  without changing existing route signatures. Login is constant-time (no user enumeration) and
  the cookie honors `X-Forwarded-Proto`/`ORC_COOKIE_SECURE` behind a TLS proxy.

### Security
- All `/api/*` routes except `/api/auth/login`, `/api/auth/logout` and `/health` require a
  valid user session (401 otherwise).

## [1.4.0] - 2026-10-16

### Added
- **Central session registry / presence** incorporated into the Orc: triple identity
  (hostname, agent_id, session_id), heartbeat-based liveness, and claims — resolving
  cross-session conflicts by session_id.

## [1.3.0] - 2026-10-15

### Added
- **OAuth2 resource-server authentication** (opt-in, `MCP_OAUTH_ENABLED`, default off):
  opaque pre-shared tokens verified via FastMCP's native `TokenVerifier`. Second barrier
  behind the nginx edge basic auth (ADR-004). `/health` stays public. Pluggable verifier so a
  future JWT/IdP (corporate SSO) can replace it without touching the rest of the service.
- **Per-request agent attribution (`agent_id`)** (ADR-005): writes record who performed them
  via `created_by`/`updated_by` on `work_items`, `created_by` on `notes` and `dependencies`.
  Resolution precedence: explicit arg → `X-Agent-ID` header → `MCP_AGENT_ID` env → OAuth
  client_id → null. Resolved per request via a contextvar with mandatory reset (no leakage
  between requests). Additive, nullable migration — anonymous writes still succeed.
- `get_project_graph_metrics` tool — critical path, impact scores, and bottleneck detection
  over the dependency graph (previously planned).

### Changed
- **Internal refactor:** the monolithic `engine.py` (~1960 LOC) was split into an `engine/`
  package of 11 cohesive modules (`base`, `items`, `transitions`, `dependencies`, `notes`,
  `queries`, `trees`, `metrics`, `archive`, `portability`, `workspace_view`) behind a
  re-export facade. **No public API change** — all tools, signatures, and the `engine.X`
  import surface are preserved. Improves maintainability and navigation.
- CI hardening: ruff config pinned (`[tool.ruff]`), actions SHA-pinned, per-job timeouts,
  docs-only `paths-ignore`, and a markdown link-check workflow.

### Fixed
- `import_graph` now orders items topologically (parent-before-child at any depth), fixing a
  `FOREIGN KEY constraint failed` crash on hierarchies ≥3 levels deep. Orphan parents are
  normalized to roots instead of crashing. Removes the FK-off workaround used during the
  cutover.
- `AGENTS.md` architecture section now reflects the real module layout (it described modules
  that never existed).

## [1.2.1] - 2026-06-23

### Added
- `parent_id` is now updatable via `manage_items(update)` — enables reparenting items between ARCs
- Validation: parent exists, no self-parent, max depth 4. Set to `""` to unparent.

## [1.2.0] - 2026-06-23

### Added
- `/health` endpoint via `@mcp.custom_route` (GET, returns status/version/uptime)

## [1.1.0] - 2026-06-08

### Added
- `get_execution_stack` tool — context stack for session resume after interruptions
- `manage_archive` tool — auto-archive done items older than N days
- `manage_checkpoints` tool — create/list/restore/verify JSON snapshots
- `get_workspace_context` tool — workspace payload at 3 verbosity levels (minimal/standard/full)
- Workspace `repos` and `conventions` fields

### Changed
- Test suite expanded to 114+ tests

## [1.0.0] - 2026-05-28

### Added
- **StreamableHTTP transport** on port 3201 (`MCP_TRANSPORT=streamable-http`)
- systemd service support (task-orchestrator.service)
- `manage_workspaces` tool — create/update/delete/list workspace configs
- Workspace-scoped queries in `get_context`, `get_next_item`, `get_metrics`
- `export_graph` and `import_graph` tools with workspace/tag filtering
- Kanban Web UI skeleton (FastAPI + HTMX + Tailwind)

### Changed
- Default transport remains stdio for backward compatibility

## [0.9.0] - 2026-05-18

### Added
- Workspace entity — tag mapping, memory_tags, description
- Workspace-filtered `get_context`, `get_next_item`, `get_metrics`
- Memory tag bridge (2 levels: inline + reference via memory service)
- Auto-checkpoint JSON resilience (corruption recovery)

## [0.8.0] - 2026-05-10

### Added
- Scheduling support (cron expressions, `next_run_at`)
- `due_at` field on work items with deadline alerts

### Fixed
- croniter naive/aware datetime handling
- CI pipeline stabilization

## [0.7.0] - 2026-05-06

### Added
- `get_metrics` tool — throughput per week, lead time, WIP, stale ratio
- Priority and tag breakdowns in metrics
- Configurable lookback period (days param)
- `complete_tree` tool — batch-complete descendants in topological order
- `create_work_tree` — atomically create root + children + dependencies

## [0.6.1] - 2026-05-02

### Added
- Comprehensive test suite with 35+ tests (#9)

### Changed
- Comprehensive README rewrite (#11)

## [0.6.0] - 2026-05-02

### Added
- Stale item detection in get_context (#4)
- Structured ToolError responses (#3)
- Filter query_items by tags (#2)
- Short hex ID resolution (4+ chars) (#1)

## [0.5.0] - 2026-04-10

### Added
- Full feature parity with original Kotlin task-orchestrator

## [0.4.0] - 2026-04-10

### Added
- Auto-reopen parent items from terminal status
- `unblock_at` threshold for dependencies
- README documentation

## [0.3.0] - 2026-04-10

### Added
- MCP prompts (workflow skills)
- Note schema gates

## [0.2.0] - 2026-04-10

### Added
- Full feature parity with original task-orchestrator
- Note schemas with gate enforcement
- Lifecycle modes
- GitHub Actions workflow for PyPI trusted publishing
- Initial Python port of task-orchestrator

[Unreleased]: https://github.com/filhocf/task-orchestrator-py/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/filhocf/task-orchestrator-py/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/filhocf/task-orchestrator-py/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/filhocf/task-orchestrator-py/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/filhocf/task-orchestrator-py/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/filhocf/task-orchestrator-py/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/filhocf/task-orchestrator-py/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/filhocf/task-orchestrator-py/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/filhocf/task-orchestrator-py/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/filhocf/task-orchestrator-py/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/filhocf/task-orchestrator-py/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/filhocf/task-orchestrator-py/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/filhocf/task-orchestrator-py/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/filhocf/task-orchestrator-py/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/filhocf/task-orchestrator-py/releases/tag/v0.2.0
