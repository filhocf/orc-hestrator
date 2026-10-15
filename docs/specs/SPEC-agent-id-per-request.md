# SPEC — agent_id per-request (actor attribution) for the Orc service

> WI 2ea10e5a · product task-orchestrator-py · implements ADR-005.
> Gate: G0 ✓ (seven; FastMCP get_context header read confirmed) → G3 RED → G4 → G5.
> Decision (Claudio, 15/out): FULL scope (work_items + notes + dependencies) — 1.3.0 not
> released yet, so no version cost in doing it all. Strategy: **contextvar**.

## Context (G0 verified)

With N agents (Zero ×3 machines, T'Pol, Scotty, subagents) on one central service, the Orc
must record WHO performed each write. ADR-005 precedence: explicit arg → `X-Agent-ID`
header → env `MCP_AGENT_ID` → (fallback) OAuth `AccessToken.client_id` → null. Semantics:
persona (zero/tpol/scotty), not harness.

Mechanism (verified): inside a FastMCP tool, `mcp.get_context().request_context.request.headers`
exposes the Starlette request headers (works under stateless_http). `RequestContext` also has
`meta` (MCP `_meta`). Resolve once at the tool boundary, store in a **contextvar**, read at the
INSERT point — keeps the ~21 engine/tool signatures unchanged and propagates across async.

## Requirements (EARS)

- **R1 (Ubiquitous):** The service SHALL resolve an `agent_id` per request with precedence:
  explicit arg → `X-Agent-ID` header → env `MCP_AGENT_ID` → OAuth `AccessToken.client_id` → null.
- **R2 (Event-driven):** WHEN a write operation creates a row in `work_items`, `notes`, or
  `dependencies`, the service SHALL record the resolved `agent_id` as `created_by`.
- **R3 (Event-driven):** WHEN a write operation updates a `work_items` row, the service SHALL
  record the resolved `agent_id` as `updated_by`.
- **R4 (Unwanted):** IF no `agent_id` can be resolved, THEN the service SHALL store NULL and the
  operation SHALL still succeed (anonymous write is acceptable — ADR-005).
- **R5 (Ubiquitous, CRITICAL):** The agent_id contextvar SHALL be set at the start of each request
  and reset at its end, so a persona from one request NEVER leaks into another (stateless_http
  reuses workers). This SHALL be covered by a test that interleaves two requests with different
  personas.
- **R6 (Ubiquitous):** The schema change SHALL be additive and nullable (`created_by`/`updated_by`
  columns default NULL), breaking neither existing rows nor the 157 current tests.
- **R7 (Ubiquitous / separation):** agent_id resolution SHALL remain independent of OAuth2
  authentication (ADR-004/R11): `X-Agent-ID` is the primary source; `AccessToken.client_id` is only
  a late fallback. The design SHALL NOT require OAuth to be enabled.
- **R8 (Ubiquitous):** Public read responses (`get_item`, `get_context`, etc.) SHALL expose the
  `created_by`/`updated_by` fields (they come through `SELECT *` / `_row_to_dict`).
- **R9 (Ubiquitous):** export_graph SHALL include the authorship columns and import_graph SHALL
  preserve them (round-trip keeps authorship).
- **R10 (Unwanted):** IF the `X-Agent-ID` header value is empty or whitespace, THEN it SHALL be
  treated as absent (fall through to the next precedence level).

## Acceptance criteria (verifiable)

1. Tool call with `X-Agent-ID: zero` → created row has `created_by='zero'`.
2. Explicit arg beats header; header beats env; env beats OAuth client_id; none → NULL.
3. Two interleaved requests (persona A then B) → each row attributed correctly, no leak (R5).
4. advance_item/update → `updated_by` set; create → `created_by` set, on all three tables.
5. 157 existing tests stay green (additive migration, signatures unchanged).
6. export then import on a fresh DB → `created_by`/`updated_by` preserved.

## Implementation shape (G4 target)

- `engine/base.py`: a `contextvar` `_current_agent_id` + `set_agent_id(v)` / `get_agent_id()` helpers.
  Writers read `get_agent_id()` at INSERT time (no signature change).
- Boundary resolution: a small helper (in auth.py or a new context helper) reads precedence from the
  FastMCP request context; called at the start of each tool in server.py (or via a wrapper), and the
  contextvar is RESET in a finally (R5). Decide the least-invasive hook in G4 (per-tool set/reset vs
  a middleware/decorator) — must guarantee reset.
- `db.py`: additive migrations — `work_items.created_by`, `work_items.updated_by`,
  `notes.created_by`, `dependencies.created_by` (all TEXT DEFAULT NULL). Mind the `_run_migrations`
  column-name check (prefix the migration key per table to avoid collision across tables).
- Writers to touch (G0 inventory): items.create_item/update_item (+ batches), notes.upsert_note,
  dependencies.add_dependency (+ pattern), trees.create_work_tree; transitions.advance_item sets
  updated_by. portability export/import carries the columns.

## Out of scope (this WI)
Presence/claims (ADR-002, next fatia — will consume agent_id). UI showing "who did what" (F018).
Changing OAuth2. Harness-vs-persona distinction beyond the persona string.
