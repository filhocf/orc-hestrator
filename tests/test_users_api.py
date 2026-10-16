"""RED tests (GATE 3) for F3 — user management REST API (admin-only).

These tests MUST FAIL today: the routes GET /api/users and POST /api/users DO NOT
EXIST yet in web/api.py, so authenticated requests hit the catch-all and return 404.
After G4 adds the two routes (both behind Depends(require_admin)), these turn GREEN.

Reuses the F1 primitives that already exist on branch feat/user-auth:
  * engine.create_user(username, password, role, created_by) -> public dict (no hash).
    Raises ToolError("CONFLICT", ...) on a duplicate username (COLLATE NOCASE) and
    ToolError("VALIDATION", ...) on an invalid role / empty field.
  * web/api.require_admin: 401 without a session, 403 if the session role != "admin".
  * TestClient persists the orc_session cookie set by POST /api/auth/login.

CONTRACT the G4 implementation MUST satisfy:
  * GET  /api/users  (require_admin) -> 200 {"users":[...]} where each user carries
    the whitelist {id, username, role, active, created_at, last_login_at} and NEVER
    password_hash / password.
  * POST /api/users  (require_admin) body {username, password, role} -> 200/201 with
    the created public user (no hash/password); role must be in {admin, user} (else
    400 VALIDATION); duplicate username -> 409 CONFLICT.
"""

import pytest
from fastapi.testclient import TestClient

from task_orchestrator import engine
from task_orchestrator.web.api import build_rest_app

# Fields the GET /api/users serializer is allowed to expose (never the hash).
_PUBLIC_FIELDS = {"id", "username", "role", "active", "created_at", "last_login_at"}


@pytest.fixture()
def app():
    return build_rest_app()


def _mk_user(username, password="pw-12345", role="user"):
    return engine.create_user(
        username=username, password=password, role=role, created_by="user:system"
    )


def _client_as(app, username, password="pw-12345"):
    """A TestClient logged in as the given (already-created) user."""
    c = TestClient(app)
    resp = c.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return c


@pytest.fixture()
def admin_client(app):
    _mk_user("root-admin", role="admin")
    return _client_as(app, "root-admin")


@pytest.fixture()
def user_client(app):
    _mk_user("plain-user", role="user")
    return _client_as(app, "plain-user")


# --- GET /api/users ---------------------------------------------------------
def test_get_users_as_admin_lists_without_hash(admin_client):
    """Admin GET -> 200, every user exposed WITHOUT password_hash, only whitelist fields."""
    _mk_user("alice", role="user")
    resp = admin_client.get("/api/users")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    users = body["users"] if isinstance(body, dict) and "users" in body else body
    assert isinstance(users, list)
    usernames = {u["username"] for u in users}
    assert {"root-admin", "alice"} <= usernames
    # hard requirement: NEVER leak the hash (neither the field nor the value)
    assert "scrypt$" not in resp.text
    for u in users:
        assert "password_hash" not in u, f"hash leaked: {u}"
        assert "password" not in u, f"password leaked: {u}"
        assert set(u.keys()) <= _PUBLIC_FIELDS, f"unexpected field exposed: {u.keys()}"


def test_get_users_as_plain_user_forbidden_403(user_client):
    """A non-admin session is rejected by require_admin -> 403."""
    resp = user_client.get("/api/users")
    assert resp.status_code == 403, resp.text


def test_get_users_without_session_unauthorized_401(app):
    """No session cookie -> 401 (require_admin / R9 boundary)."""
    c = TestClient(app)
    resp = c.get("/api/users")
    assert resp.status_code == 401, resp.text


# --- POST /api/users --------------------------------------------------------
def test_post_users_as_admin_creates_and_hides_secret(admin_client):
    """Admin POST -> created user visible on GET, body never echoes the secret."""
    resp = admin_client.post(
        "/api/users",
        json={"username": "bob", "password": "bob-secret-pw", "role": "user"},
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    created = body["user"] if isinstance(body, dict) and "user" in body else body
    assert created["username"] == "bob"
    assert created["role"] == "user"
    # the secret must never come back
    assert "password" not in created
    assert "password_hash" not in created
    assert "bob-secret-pw" not in resp.text
    assert "scrypt$" not in resp.text

    # GET confirms it now appears
    got = admin_client.get("/api/users")
    assert got.status_code == 200, got.text
    gb = got.json()
    users = gb["users"] if isinstance(gb, dict) and "users" in gb else gb
    assert "bob" in {u["username"] for u in users}


def test_post_users_as_plain_user_forbidden_403(user_client):
    """A non-admin may not create users -> 403."""
    resp = user_client.post(
        "/api/users",
        json={"username": "mallory", "password": "x-pw-12345", "role": "user"},
    )
    assert resp.status_code == 403, resp.text
    # and it must NOT have been created
    assert engine.get_user("mallory") is None


def test_post_users_duplicate_username_conflict(admin_client):
    """Duplicate username -> ToolError CONFLICT mapped to 409 (engine raises CONFLICT)."""
    first = admin_client.post(
        "/api/users",
        json={"username": "dupe", "password": "pw-12345", "role": "user"},
    )
    assert first.status_code in (200, 201), first.text
    second = admin_client.post(
        "/api/users",
        json={"username": "dupe", "password": "pw-67890", "role": "user"},
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "CONFLICT"


def test_post_users_invalid_role_400(admin_client):
    """A role outside {admin, user} -> 400 VALIDATION."""
    resp = admin_client.post(
        "/api/users",
        json={"username": "weirdo", "password": "pw-12345", "role": "superuser"},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION"
    assert engine.get_user("weirdo") is None
