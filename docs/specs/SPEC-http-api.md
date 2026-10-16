# SPEC — Orc HTTP/REST API (for the decoupled management UI)

> WI 7811c1ac (UI 1.5.0) — backend half. product task-orchestrator-py.
> Gate: G0 ✓ (seven; mount verified: streamable_http_app() is a mutable Starlette with preserved
> lifespan) → G3 RED → G4 → G5. Thin layer over the existing engine — reuse, no new logic.
> Context: the Orc exposes MCP (agents); the decoupled human UI (React, from Stitch) needs REST.

## Requirements (EARS) — from G0

- **R1** The system SHALL expose a JSON REST API under `/api`, mounted as a FastAPI sub-app on the
  Starlette app returned by `streamable_http_app()`, served by the same Orc service instance/port.
- **R2** WHEN a GET read endpoint is called, the system SHALL call the corresponding engine read
  function (table below) and return its result as JSON, WITHOUT reimplementing logic.
- **R3** The system SHALL support, in v1, the reads: items (filters status/tags/parent/priority/
  search + pagination), items/{id} (children/notes/deps/claim/authorship), arcs, arcs/{id},
  context, sessions, claims, metrics, metrics/graph, graph/{arc}, workspaces.
- **R4** WHEN the engine raises `ToolError`, the system SHALL map `code`→HTTP status (NOT_FOUND→404,
  VALIDATION→400, CONFLICT→409, DEPENDENCY_UNSATISFIED→422, GATE_BLOCKED→422) and return
  `ToolError.to_dict()` as the body.
- **R5** WHEN a non-ToolError exception occurs, the system SHALL return 500 with
  `{"error":{"code":"INTERNAL",...}}` without leaking a stacktrace.
- **R6** The system SHALL apply `CORSMiddleware` with origins from `MCP_UI_CORS_ORIGINS`
  (dev default `http://localhost:5173`), NEVER `*` with credentials.
- **R7** WHEN a write (advance/claim/release) is called, the system SHALL resolve the human actor
  and set the `agent_id` contextvar (via `set_agent_id`) for the request scope, resetting it at the
  end, so `created_by`/`updated_by` reflect the UI user.
- **R8** The system SHALL support in v1 only the writes `PATCH /api/items/{id}/advance`,
  `POST /api/claims`, `DELETE /api/claims`; other writes are phase 2.
- **R9** The system SHALL keep `/api` routes outside the MCP `RequireAuthMiddleware` and, in v1,
  protect them via nginx basic-auth, WITHOUT coupling to the agent OAuth.
- **R10** The system SHALL expose a single identity/authorization extension point (dependency
  `get_current_user`) that in v1 resolves a generic actor / `X-Forwarded-User`, and in 1.5.0 begins
  validating user session + RBAC WITHOUT changing route signatures.
- **R11** WHEN `MCP_TRANSPORT=stdio`, the system SHALL NOT mount the REST API (behavior identical to
  today for local agents).
- **R12** The composed app SHALL preserve the FastMCP session-manager `lifespan` (else `/mcp` breaks)
  when served by its own uvicorn.

## Endpoint → engine function (reuse, no new logic)

| Endpoint | Engine call |
|---|---|
| `GET /api/items` | `query_items(status/tags/parent_id/priority/search, limit, offset)` |
| `GET /api/items/{id}` | `get_context(id)` + `get_notes` + `get_dependencies` + `get_claim_for` |
| `GET /api/arcs` | `query_items(tags="arc")` |
| `GET /api/arcs/{id}` | `get_children` (tree) |
| `GET /api/context` | `get_context()` (dashboard: counts/active/blocked/next) |
| `GET /api/sessions` | `presence_list(hostname?, agent_id?)` |
| `GET /api/claims?subject=...` | `get_claim_for` / `conflicts` |
| `GET /api/metrics` | `get_metrics` |
| `GET /api/metrics/graph` | `get_project_graph_metrics` |
| `GET /api/graph/{arc}` | cytoscape builder (extract from ui/ legacy to web/graph.py) |
| `GET /api/workspaces` | `list_workspaces` |
| `PATCH /api/items/{id}/advance` | `advance_item(id, trigger)` |
| `POST /api/claims` / `DELETE /api/claims` | `claim` / `release` |

## Acceptance criteria (verifiable, via Starlette TestClient)

1. GET /api/items (empty DB) → 200, `{"items":[],"total":0,...}`; with items → returns them + authorship fields.
2. GET /api/items/{absent} → 404 with ToolError body (NOT_FOUND).
3. GET /api/context → 200 with counts/active/blocked.
4. GET /api/sessions after a presence_register → 200 lists the session triple.
5. PATCH /api/items/{id}/advance {trigger:start} → 200, status advanced; invalid trigger → 400/409.
6. POST /api/claims by one actor, then another actor same item → 409 CONFLICT.
7. ToolError→HTTP mapping holds for each code.
8. CORS preflight (OPTIONS) from the dev origin → allowed; unknown origin → not allowed.
9. stdio transport → no /api mounted (R11).
10. /mcp and /health still work with /api mounted (R12 — lifespan preserved). 194 existing tests pass.

## Implementation shape (G4)
- New `src/task_orchestrator/web/api.py` (FastAPI sub-app) + `web/graph.py` (cytoscape builder
  extracted from the legacy ui/, pure fn). Mount on `streamable_http_app()` in server.main() ONLY
  when transport == streamable-http. ToolError handler + CORS middleware on the sub-app.
  `get_current_user` dependency (v1 stub). Version from importlib.metadata (fix the 1.3.0 hardcode).
- Tests: tests/test_http_api.py via TestClient over the mounted app (no MCP handshake needed).

## Out of scope (v1 of the API)
Full CRUD via REST, login/RBAC enforcement, WebSocket/SSE realtime, `/api/v1` versioning,
retiring ui/app.py (legacy stays until the new UI replaces it).
