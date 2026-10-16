"""RED tests (GATE 3) for F1 — user authentication + RBAC (SPEC-user-auth-rbac).

These tests MUST FAIL today: `engine.users`/`engine.create_user`/`engine.seed_admin`
and the `/api/auth/*` routes + session-cookie `get_current_user` DO NOT EXIST yet.
After G4 implements engine/users.py, db migrations, web/api.py auth and server seed,
these turn GREEN.

The 12 acceptance criteria of the SPEC map to the tests below:
  AC1  seed idempotent              -> test_seed_admin_idempotent
  AC2  login ok -> cookie + user    -> test_login_correct_sets_httponly_cookie_and_returns_user
  AC3  login wrong/unknown -> 401    -> test_login_wrong_password_and_unknown_user_identical_401
  AC4  /me with/without cookie       -> test_me_with_cookie / test_me_without_cookie_401
  AC5  /api/context needs session    -> test_protected_route_requires_session
  AC6  logout revokes + 204          -> test_logout_revokes_session_and_clears_cookie
  AC7  user-role -> admin route 403  -> test_rbac_user_on_admin_route_403
  AC8  advance -> updated_by user:   -> test_advance_sets_updated_by_to_session_user
  AC9  hash scrypt$, never leaked    -> test_hash_format_scrypt_and_never_leaked
  AC10 only login+health public      -> test_only_login_and_health_public
  AC11 expired session -> 401        -> test_expired_session_rejected
  AC12 212 existing tests pass       -> enforced by the full suite run (not here)
"""

import pytest
from fastapi.testclient import TestClient

from task_orchestrator import engine
from task_orchestrator.web.api import build_rest_app


@pytest.fixture()
def app():
    return build_rest_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


def _mk_admin(username="admin", password="s3cret-pw", role="admin"):
    """Create a user directly through the engine (bypass HTTP) for setup."""
    return engine.create_user(
        username=username, password=password, role=role, created_by="user:system"
    )


def _login(client, username, password):
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


# --- AC1: seed idempotent ---------------------------------------------------
def test_seed_admin_idempotent(monkeypatch):
    monkeypatch.setenv("ORC_ADMIN_USER", "admin")
    monkeypatch.setenv("ORC_ADMIN_PASSWORD", "boot-pw-123")
    engine.seed_admin()
    engine.seed_admin()  # second startup must not create a duplicate
    users = engine.list_users()
    admins = [u for u in users if u["username"] == "admin"]
    assert len(admins) == 1, admins
    assert admins[0]["role"] == "admin"


def test_seed_admin_absent_env_does_not_crash(monkeypatch):
    monkeypatch.delenv("ORC_ADMIN_USER", raising=False)
    monkeypatch.delenv("ORC_ADMIN_PASSWORD", raising=False)
    engine.seed_admin()  # R11: must not raise
    assert engine.list_users() == []


# --- AC2: login correct -> cookie + user (no hash) --------------------------
def test_login_correct_sets_httponly_cookie_and_returns_user(client):
    _mk_admin()
    resp = _login(client, "admin", "s3cret-pw")
    assert resp.status_code == 200, resp.text
    set_cookie = resp.headers.get("set-cookie", "")
    assert "orc_session=" in set_cookie
    assert "httponly" in set_cookie.lower()
    body = resp.json()
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "admin"
    # never leak the hash
    assert "password_hash" not in body["user"]
    assert "scrypt$" not in resp.text


def test_login_case_insensitive_username(client):
    _mk_admin(username="Admin")
    resp = _login(client, "admin", "s3cret-pw")
    assert resp.status_code == 200, resp.text


# --- AC3: wrong/unknown -> identical generic 401 (no enumeration) -----------
def test_login_wrong_password_and_unknown_user_identical_401(client):
    _mk_admin()
    wrong = _login(client, "admin", "nope")
    unknown = _login(client, "ghost", "whatever")
    assert wrong.status_code == 401
    assert unknown.status_code == 401
    # R4: same generic body, no user enumeration
    assert wrong.json() == unknown.json()


def test_login_inactive_user_401(client):
    _mk_admin(username="bob", role="user")
    engine.set_user_active("bob", False)
    resp = _login(client, "bob", "s3cret-pw")
    assert resp.status_code == 401


# --- AC4: /me with and without cookie ---------------------------------------
def test_me_with_cookie(client):
    _mk_admin()
    _login(client, "admin", "s3cret-pw")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["username"] == "admin"


def test_me_without_cookie_401(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


# --- AC5: protected route requires a session --------------------------------
def test_protected_route_requires_session(client):
    # without session -> 401
    anon = client.get("/api/context")
    assert anon.status_code == 401
    # with session -> 200
    _mk_admin()
    _login(client, "admin", "s3cret-pw")
    ok = client.get("/api/context")
    assert ok.status_code == 200, ok.text


# --- AC6: logout revokes + idempotent 204 -----------------------------------
def test_logout_revokes_session_and_clears_cookie(client):
    _mk_admin()
    _login(client, "admin", "s3cret-pw")
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    # reusing the (now revoked) session -> 401
    me = client.get("/api/auth/me")
    assert me.status_code == 401


def test_logout_without_session_is_idempotent_204(client):
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 204


# --- AC7: RBAC — user role on an admin-only route -> 403 --------------------
def test_rbac_user_on_admin_route_403(app, client):
    from fastapi import Depends

    from task_orchestrator.web.api import require_admin

    # Add a throwaway admin-only route exercising require_admin.
    @app.get("/api/_admin_probe")
    def _probe(_actor: str = Depends(require_admin)) -> dict:
        return {"ok": True}

    _mk_admin(username="bob", role="user")
    _login(client, "bob", "s3cret-pw")
    resp = client.get("/api/_admin_probe")
    assert resp.status_code == 403, resp.text

    # and an admin passes
    client.post("/api/auth/logout")
    _mk_admin(username="root", role="admin")
    _login(client, "root", "s3cret-pw")
    ok = client.get("/api/_admin_probe")
    assert ok.status_code == 200, ok.text


# --- AC8: advance sets updated_by to the session user (R13) -----------------
def test_advance_sets_updated_by_to_session_user(client):
    _mk_admin()
    _login(client, "admin", "s3cret-pw")
    item = engine.create_item(title="to-advance")
    resp = client.patch(f"/api/items/{item['id']}/advance", json={"trigger": "start"})
    assert resp.status_code == 200, resp.text
    refreshed = engine.get_item(item["id"])
    assert refreshed["updated_by"] == "user:admin"


# --- AC9: hash format scrypt$ and never leaked ------------------------------
def test_hash_format_scrypt_and_never_leaked(client):
    user = _mk_admin()
    stored = engine.get_user("admin")
    assert stored["password_hash"].startswith("scrypt$")
    # the plaintext must never be embedded in the hash
    assert "s3cret-pw" not in stored["password_hash"]
    # create_user return must not leak the hash
    assert "password_hash" not in user or user.get("password_hash") is None
    # verify_credentials works both ways
    assert engine.verify_credentials("admin", "s3cret-pw") is not None
    assert engine.verify_credentials("admin", "wrong") is None


# --- AC10: only /api/auth/login and /health are public ----------------------
def test_only_login_and_health_public(client):
    # login reachable without a session (wrong creds still -> 401, but NOT the
    # generic auth-required 401 for missing session; it processes the body)
    r_login = client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert r_login.status_code == 401  # bad creds, but the route ran

    r_health = client.get("/health")
    assert r_health.status_code == 200, r_health.text

    # a sample of other /api/* routes must all require a session
    for path in ("/api/items", "/api/context", "/api/arcs", "/api/workspaces"):
        assert client.get(path).status_code == 401, path


# --- AC11: expired session -> 401 -------------------------------------------
def test_expired_session_rejected(client, monkeypatch):
    _mk_admin()
    # TTL 0 hours -> the session is already expired at creation
    monkeypatch.setenv("ORC_SESSION_TTL_HOURS", "0")
    _login(client, "admin", "s3cret-pw")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_health_endpoint_exists(client):
    assert client.get("/health").status_code == 200
