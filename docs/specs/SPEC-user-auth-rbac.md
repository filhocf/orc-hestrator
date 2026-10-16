# SPEC — Orc user authentication + RBAC (for the management UI)

> WI 0af766c6 (SUB-ARC: conectar UI 1.5.0 ao Orc real com auth) → F1 (7e2204be).
> product task-orchestrator-py, 1.5.0. Gate: G0 → G3 RED → G4 → G5.
> Context: the REST API (`web/api.py`, SPEC-http-api) left `get_current_user` as the single
> identity/authz extension point (R10) explicitly to grow into real user-session + RBAC WITHOUT
> changing route signatures. This spec fills that point. Distinct from the agent OAuth
> (`auth.py`, SPEC-oauth2-resource-server) which protects the MCP for AGENTS — this is for HUMANS
> on the UI. Claudio (16/out): "precisa de um usuário admin para começar" — real auth, not stub.

## Architecture decisions (G0, justified)

- **Password hashing: `hashlib.scrypt` (stdlib), NOT a new dependency.** The project is zero-ML-dep
  and ships to a small VPS; scrypt is in the stdlib, memory-hard, and sufficient for a small team.
  (bcrypt/argon2 via passlib would add a C dependency for marginal gain at this scale. Revisit if
  the user base grows.) Per-user random salt; store `scrypt$n$r$p$salt$hash`.
- **Session: signed opaque token in an HTTP-only cookie.** Server generates a random token (secrets),
  stores `(token_hash, user_id, expires_at)` in a `user_sessions` table, sets it as an HTTP-only,
  SameSite=Lax, Secure (in prod) cookie `orc_session`. Stateless JWT rejected: we want server-side
  revocation (logout, disable user) and the DB is already there. Token is hashed at rest.
- **RBAC: two roles, `admin` and `user`.** Enough for "an admin to start". `admin` manages users;
  both can read/act on work items. Finer-grained perms are future.
- **Admin seed via env, never hardcoded.** On startup, if `ORC_ADMIN_USER` + `ORC_ADMIN_PASSWORD`
  are set AND no admin exists, create the initial admin. Logged (without the password).

## Requirements (EARS)

- **R1** The system SHALL persist users in a `users` table: `id` (uuid), `username` (unique,
  case-insensitive), `password_hash`, `role` (`admin`|`user`), `active` (bool, default 1),
  `created_at`, `created_by`, `last_login_at` (nullable).
- **R2** The system SHALL hash passwords with `hashlib.scrypt` using a per-user random salt, and
  SHALL NEVER store or log plaintext passwords. Verification SHALL use a constant-time comparison.
- **R3** WHEN `POST /api/auth/login` receives valid `{username, password}` for an `active` user,
  the system SHALL create a server-side session, set the `orc_session` HTTP-only cookie
  (SameSite=Lax; Secure when not localhost), update `last_login_at`, and return
  `{user:{username, role}}` (NEVER the hash).
- **R4** WHEN `POST /api/auth/login` receives wrong credentials, an unknown user, or an inactive
  user, the system SHALL return 401 with a generic message (NO user-enumeration: same response for
  unknown user and wrong password).
- **R5** The system SHALL persist sessions in `user_sessions` (`token_hash`, `user_id`, `expires_at`,
  `created_at`); the cookie SHALL carry only the opaque token, and the table SHALL store its hash.
- **R6** WHEN `POST /api/auth/logout` is called with a valid session, the system SHALL delete that
  server-side session and clear the cookie (idempotent: always 204).
- **R7** WHEN `GET /api/auth/me` is called with a valid session, the system SHALL return
  `{user:{username, role}}`; with no/expired/invalid session → 401.
- **R8** The system SHALL implement `get_current_user(request)` (the SPEC-http-api R10 extension
  point) to resolve the human actor FROM THE SESSION COOKIE: valid session → `user:<username>`;
  else → 401 on protected routes. The dependency signature of existing routes SHALL NOT change.
- **R9** The system SHALL protect all `/api/*` routes EXCEPT `/api/auth/login` and `/health`:
  a missing/invalid session on a protected route SHALL return 401.
- **R10** The system SHALL enforce RBAC: routes tagged admin-only (user management, F3) SHALL
  return 403 when the session user's role is not `admin`. Non-admin-only routes allow any
  authenticated user.
- **R11** WHEN the service starts AND `ORC_ADMIN_USER`+`ORC_ADMIN_PASSWORD` are set AND no `admin`
  user exists, the system SHALL create that initial admin (idempotent: never overwrite an existing
  admin; never recreate on restart). Absence of the env vars SHALL NOT crash startup.
- **R12** Sessions SHALL expire after `ORC_SESSION_TTL_HOURS` (default 168 = 7 days); expired
  sessions SHALL be rejected and MAY be pruned lazily on access.
- **R13** WHEN a write (advance/claim/release) runs, `created_by`/`updated_by` SHALL reflect the
  authenticated user (`user:<username>`), via the existing `set_agent_id` contextvar mechanism
  (SPEC-http-api R7) — no route signature change.

## Endpoints

| Endpoint | Method | Auth | Behavior |
|---|---|---|---|
| `/api/auth/login` | POST | public | validate creds → set cookie, return user |
| `/api/auth/logout` | POST | session | delete session, clear cookie (204) |
| `/api/auth/me` | GET | session | current user or 401 |

(User-management endpoints `/api/users` are specified in F3; this spec only requires the RBAC
hook `require_admin` to exist.)

## Acceptance criteria (verifiable, via Starlette/FastAPI TestClient)

1. Seed: with `ORC_ADMIN_USER=admin`/`ORC_ADMIN_PASSWORD=...` on empty DB → one admin user exists;
   second startup → still exactly one (idempotent).
2. `POST /api/auth/login` correct creds → 200, `Set-Cookie: orc_session=...; HttpOnly`, body has
   `user.role=admin`, no hash in body.
3. `POST /api/auth/login` wrong password OR unknown user → 401, identical generic body (R4).
4. `GET /api/auth/me` with the cookie → 200 user; without cookie → 401.
5. `GET /api/context` without session → 401 (R9); with session → 200.
6. `POST /api/auth/logout` → 204, and reusing the old cookie on `/api/auth/me` → 401 (R6).
7. A `user`-role session hitting an admin-only route → 403 (R10).
8. `PATCH /api/items/{id}/advance` while logged in as `admin` → item `updated_by == "user:admin"` (R13).
9. Password never appears in logs or responses; hash format is `scrypt$...` (R2).
10. `/api/auth/login` and `/health` reachable WITHOUT a session; all other `/api/*` require it (R9).
11. Expired session (ttl past) → 401 (R12).
12. Existing 212 API/engine tests still pass (no route signature changes).

## Implementation shape (G4)

- `db.py`: `CREATE TABLE IF NOT EXISTS users (...)` + `user_sessions (...)` (migration, same pattern).
- New `engine/users.py` (or `auth_users.py`): `create_user`, `verify_credentials`, `get_user`,
  `list_users`, `scrypt` hash/verify, session create/lookup/delete/prune. Pure functions over `db`.
- `web/api.py`: `/api/auth/*` routes; rewrite `get_current_user` to read the `orc_session` cookie and
  validate via engine; add `require_admin` dependency; wrap protected routes (middleware or a
  shared dependency) enforcing R9. Admin seed called from `server.main()` startup.
- Tests: `tests/test_user_auth.py` via TestClient (login/logout/me/RBAC/seed/expiry).

## Out of scope (this phase)
Password reset flows, email, MFA, OAuth/SSO for humans, per-item ACLs, rate-limiting on login
(nginx can throttle). User CRUD UI is F3. These are future.
