# SPEC — OAuth2 (resource-server, opaque token) for the Orc service

> WI d261140f · product task-orchestrator-py · implements ADR-004 (nginx basic + OAuth2 second barrier).
> Gate: G0 ✓ (seven, FastMCP native resource-server confirmed) → G3 RED → G4 → G5.
> Decision (Claudio, 15/out): **opaque pre-shared token** — option (c). No `/token`, no JWT/RSA in v0.1.

## Context (G0 verified)

FastMCP (mcp 1.27.0) supports native resource-server auth: pass `token_verifier` + `auth`
to `FastMCP(...)`. Implementing OAuth2 here = configure that + write ONE `TokenVerifier`
(a class with one async method `verify_token(token) -> AccessToken | None`). NOT an
authorization server (contrast: memory-service ships 4735 LOC of full OAuth — over-kill
here). `client_credentials` is a grant, not a token format; an opaque pre-shared token
satisfies ADR-004. `/health` stays public (FastMCP attaches custom_routes outside the
auth middleware — verified in source).

## Requirements (EARS)

- **R1 (Ubiquitous):** The Orc service SHALL expose a config flag `MCP_OAUTH_ENABLED`, default `false`.
- **R2 (State-driven):** WHILE `MCP_OAUTH_ENABLED` is `false`, the service SHALL accept `/mcp`
  requests with no Bearer token — identical to current behavior (the 3 machines in production
  must not break on deploy).
- **R3 (State-driven):** WHILE `MCP_OAUTH_ENABLED` is `true`, the service SHALL require a valid
  Bearer token on every `/mcp` request and reject a missing one with HTTP 401.
- **R4 (Event-driven):** WHEN a request presents a Bearer token matching a configured client
  secret, the service SHALL authenticate it and associate the request with the matching
  `client_id` (persona).
- **R5 (Unwanted):** IF a Bearer token is absent, malformed, unknown, or expired, THEN the
  service SHALL reject with HTTP 401 and SHALL NOT execute the MCP operation.
- **R6 (Ubiquitous):** The service SHALL keep `/health` publicly accessible regardless of
  `MCP_OAUTH_ENABLED`.
- **R7 (Ubiquitous):** The service SHALL use opaque pre-shared tokens and SHALL NOT implement a
  token-issuance endpoint (`/token`, `/authorize`, `/register`) in v0.1.
- **R8 (Ubiquitous):** Client secrets SHALL live outside the sync (per-machine), never in the
  repo or synced config.
- **R9 (Ubiquitous):** Token verification SHALL be pluggable — a future JWT/JWKS verifier
  (corporate IdP) SHALL replace the opaque verifier without changing the rest of the service
  (stable `TokenVerifier` interface).
- **R10 (Unwanted / coexistence):** IF the nginx edge consumes HTTP Basic credentials, THEN the
  Orc Bearer token SHALL NOT collide with `Authorization: Basic` (reserve `Authorization` for the
  edge basic — nginx consumes the URL-embedded basic and does not forward it upstream; verify
  before enabling in prod).
- **R11 (Ubiquitous / separation):** Authentication (who may enter) SHALL stay independent of
  `agent_id` resolution (who is acting, ADR-005, `X-Agent-ID`). The design SHALL NOT bind
  `agent_id` to the token.
- **R12 (Rollout, Event-driven):** WHEN enabling `MCP_OAUTH_ENABLED=true` in prod, the operator
  SHALL first distribute credentials to all clients and update each `orc-vps` config; the flag
  stays `false` until every client has credentials.

## Acceptance criteria (verifiable)

1. Flag OFF: `/mcp` with no Bearer → works (200/stream), identical to today. No client breaks.
2. Flag ON: no Bearer → 401; valid Bearer → 200; invalid/unknown/expired Bearer → 401.
3. `/health` → 200 public in BOTH flag states.
4. Coexistence smoke: basic-in-URL (nginx) + Bearer in header → 200 (no header collision).

## Implementation shape (G4 target)

- New `src/task_orchestrator/auth.py`:
  - `build_auth() -> tuple[TokenVerifier | None, AuthSettings | None]` — reads env; `MCP_OAUTH_ENABLED`
    false → returns `(None, None)`.
  - `class OpaqueTokenVerifier` — `verify_token(token)` compares constant-time against the configured
    secret set (env `MCP_OAUTH_TOKENS="persona:secret,..."` or a file outside sync); returns
    `AccessToken(token=..., client_id=<persona>, scopes=["orc"])` or `None`.
- `src/task_orchestrator/server.py`: call `build_auth()` before `FastMCP(...)` and pass
  `token_verifier=/auth=` into the constructor (validation happens in `__init__`; cannot set later).
  OFF → pass `None/None` → no middleware installed → behavior identical to today.
- Do NOT touch `stateless_http=True`. Do NOT implement agent_id here (separate fatia, ADR-005).

## Out of scope (v0.1)
Token issuance endpoint, JWT/RSA, DCR, refresh tokens, corporate IdP/Keycloak (future: swap the
verifier only), agent_id resolution (ADR-005, next fatia).
