# SPEC — session-registry (central presence + unified claim) for the Orc (1.4.0)

> WI cbe52a74 · product task-orchestrator-py · implements ADR-002 (incorporate session-registry
> as sub-domain) + ADR-005 (agent_id). Gate: G0 ✓ (seven, triple identity) → G3 RED → G4 → G5.
> Decisions (Claudio): actor identity = **triple (hostname, agent_id, session_id)**; mirror MMS
> headers X-Agent-ID + X-Client-Hostname; cli distinguishes kiro-cli/kiro-ide; unified claim
> work_item|resource with app-level validation (no physical FK on subject_ref); lazy reap.

## Context

Today presence/claim lives in a separate per-machine service (mcp-session-registry, 508 LOC).
With the central Orc on the VPS, N agents (6 Kiros on DNBSCDC289 all persona 'zero', plus
sirdata/socrates, plus tpol/scotty) need central presence so the board shows who is on what and
claim conflicts are detected across machines. The identity is a **triple**: no single level is
unique; the three together are. Presence key = session_id (uuid), always displayed as
`hostname/agent_id/session_id` (e.g. `DNBSCDC289.741/zero/sess-a1b2`). The X-Client-Hostname
header already arrives (header rollout done); this fatia gives it a home (the sessions table).

## Requirements (EARS) — from G0

- **R1 (ubiquitous):** The Orc SHALL identify an actor by the triple (hostname, agent_id,
  session_id) and SHALL use session_id as the global presence/claim key while always carrying
  hostname and agent_id for display and query.
- **R2 (ubiquitous):** The Orc SHALL persist presence in a central `sessions` table: id
  (session_id uuid PK), agent_id (nullable persona), hostname (NOT NULL), pid, cli, theme,
  status, started_at, heartbeat_at; indexed by agent_id, hostname, status, heartbeat_at.
- **R3 (event):** WHEN agent_register is invoked, the Orc SHALL generate a uuid session_id,
  resolve agent_id from context (X-Agent-ID → MCP_AGENT_ID → OAuth → None) and hostname by
  precedence (arg → X-Client-Hostname header → socket/env → 'unknown'), persist the session,
  and RETURN session_id to the client.
- **R4 (ubiquitous):** The client SHALL reuse the returned session_id as an argument to
  heartbeat, claim, and end; session_id SHALL NOT be derived from a header.
- **R5 (ubiquitous):** The Orc SHALL mirror the memory-service header names — X-Agent-ID
  (persona) and X-Client-Hostname (host) — so a single header configuration serves both products.
- **R6 (ubiquitous):** The Orc SHALL persist claims in one `claims` table with subject_type ∈
  {work_item, resource}, subject_ref, session_id (FK sessions ON DELETE CASCADE), optional
  resource_type and expires_at; the owner's triple SHALL be obtained by JOIN on sessions.
- **R7 (event):** WHEN a claim has subject_type='work_item', the Orc SHALL validate subject_ref
  against work_items.id and return NOT_FOUND if absent; subject_type='resource' SHALL accept any
  free-form subject_ref.
- **R8 (unwanted):** IF a non-expired work_item claim is held by a DIFFERENT session_id — even
  with the same agent_id and hostname — THEN the Orc SHALL return a CONFLICT ToolError
  identifying the holder's triple.
- **R9 (event):** WHEN agent_list is invoked, the Orc SHALL support optional filtering by
  hostname and/or agent_id (query by any level of the triple) and SHALL return each session's
  triple and human-readable label.
- **R10 (state-driven):** WHILE a session's heartbeat_at is older than 300s, the Orc SHALL treat
  it as dead and SHALL release its claims (CASCADE) on the next reap.
- **R11 (event):** WHEN agent_list, conflicts, or get_claim_for is invoked, the Orc SHALL lazily
  reap stale sessions (server clock, any host) before returning.
- **R12 (event):** WHEN get_context or get_next_item returns a work item, the Orc SHALL include
  the active claim with the owner's triple (hostname, agent_id, session_id, label, claimed_at,
  expires_at) when present.
- **R13 (event):** WHEN a claim's expires_at is in the past, the Orc SHALL exclude it from
  conflicts() and get_claim_for() and SHALL reap it.
- **R14 (ubiquitous):** The migration SHALL be additive and SHALL NOT alter any of the 23 existing
  tools, preserving all 177 existing tests.
- **R15 (event):** WHEN agent_end is invoked, the Orc SHALL delete the session and cascade-delete
  its claims.

## Acceptance criteria (verifiable)

1. agent_register (no args, X-Agent-ID=zero/X-Client-Hostname=h in context) → returns session_id;
   sessions row has agent_id='zero', hostname='h'.
2. Two agent_register with same agent_id+hostname → two distinct session_ids (the 6-Kiros case).
3. claim(work_item, <valid id>) by session A → ok; claim same item by session B → CONFLICT naming
   A's triple (R8 — the anti-rework guarantee, even same persona/host).
4. claim(work_item, <absent id>) → NOT_FOUND (R7); claim(resource, 'any/path') → ok.
5. agent_list filtered by hostname / by agent_id returns the right subset with triples (R9).
6. Session with heartbeat >300s → reaped on next agent_list; its claims gone (R10/R11).
7. get_context(item) with an active claim shows the holder's triple (R12).
8. expired claim excluded from conflicts/get_claim_for (R13).
9. agent_end → session + its claims deleted (R15).
10. All 177 existing tests still pass; 23 existing tools unchanged (R14).

## Implementation shape (G4 target)

- `db.py`: add `sessions` + `claims` tables to SCHEMA (CREATE IF NOT EXISTS) + defensive additive
  MIGRATIONS (ALTER ADD COLUMN) keyed per-table to avoid the created_by-style collision.
- `engine/presence.py`: register (generates session_id, resolves hostname by precedence — read
  X-Client-Hostname via the same request-context mechanism as agent_id), heartbeat, end, list_active
  (filters hostname/agent_id, lazy reap), reap. Pattern of notes.py.
- `engine/claims.py`: claim (unified, validate work_item against work_items, UNIQUE per subject,
  CONFLICT on different session_id), release, conflicts, get_claim_for. Lazy reap on reads.
- Facade engine/__init__ re-exports (presence_*/claim_*). server.py adds 7 tools (agent_register,
  agent_heartbeat, agent_end, agent_list, claim, release, conflicts) — all @with_agent_id.
- queries.get_context / get_next_item: include active claim (get_claim_for) on the returned item.
- Import DAG: claims may read work_items (items) — keep direction (claims is a leaf-ish domain;
  queries aggregates). Avoid cycle claims↔queries.

## Out of scope (1.4.0)
Cascade of work_item delete → its claims (v1.4.1). Alias session_*→agent_* compat. Scheduler/
background reap, auto lease-TTL, UI tree (1.5.0). Retiring mcp-session-registry repo (follow-up,
migrate startup/shutdown-hook + mcp.json + unit 3203). OAuth enable (separate rollout).
