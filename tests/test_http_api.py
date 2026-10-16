"""RED tests (GATE 3) for the Orc HTTP/REST API — the surface the decoupled UI consumes.

These tests MUST FAIL today: the module `task_orchestrator.web.api` and its factory
`build_rest_app()` DO NOT EXIST yet. The top-level import below therefore aborts COLLECTION
of THIS FILE with ImportError — that is valid RED (not a bug). After G4 implements
`web/api.py` with `build_rest_app()`, these turn GREEN.

Isolation guarantee: the failing import lives ONLY in this file, so the other 194 tests still
collect/pass (`pytest --ignore=tests/test_http_api.py` == 194 passed).

CONTRACT the G4 implementation MUST satisfy (pinned here, source of truth for G4):
  * Factory:   `from task_orchestrator.web.api import build_rest_app; app = build_rest_app()`
               (name per SPEC §7 / G0 §7 — NOT `create_api_app`). Returns a FastAPI app whose
               routes live under `/api` (the sub-app is mounted at `/api`; tests hit `/api/...`).
  * TestClient over the isolated sub-app, no MCP handshake (SPEC §7).
  * JSON shapes and status codes asserted below. Where a shape is a G4 decision, it is marked
    `# CONTRACT:` — G4 must implement exactly that or coordinate a change back to this file.

Engine facts used for setup (verified against src/task_orchestrator/engine):
  * engine.create_item(title, ..., tags="") -> dict (has "id", "created_by")
  * engine.presence_register(hostname, pid, cli, theme) -> {"session_id", "agent_id", "hostname", ...}
  * engine.claim(subject_type, subject_ref, session_id, ...) -> dict; a DIFFERENT session_id
    claiming the same (subject_type, subject_ref) raises ToolError("CONFLICT", ...).
  * engine.advance_item(item_id, trigger): trigger "start" moves queue -> work.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from task_orchestrator import engine

# RED: this import fails at collection today (web/api.py does not exist). Intentional.
from task_orchestrator.web.api import build_rest_app


@pytest.fixture()
def client():
    """TestClient over the isolated REST sub-app (SPEC §7 — no MCP session manager needed)."""
    return TestClient(build_rest_app())


# ---------------------------------------------------------------------------
# 1. GET /api/items — empty + populated, with authorship field
# ---------------------------------------------------------------------------
def test_items_empty_db_returns_empty_paginated_envelope(client):
    """Criterion 1: empty DB -> 200 and {"items":[],"total":0,...}."""
    resp = client.get("/api/items")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # CONTRACT: paginated collections return {items,total,limit,offset}
    assert body["items"] == []
    assert body["total"] == 0


def test_items_populated_returns_items_with_created_by(client):
    """Criterion 1: with items -> they come back, each carries the authorship field created_by."""
    a = engine.create_item(title="alpha")
    b = engine.create_item(title="beta")
    resp = client.get("/api/items")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 2
    ids = {it["id"] for it in body["items"]}
    assert {a["id"], b["id"]} <= ids
    # authorship is a hard requirement of the contract (SPEC R7 / items table)
    for it in body["items"]:
        assert "created_by" in it, "every item must expose created_by"


def test_items_status_filter_is_honored(client):
    """Filters pass through to engine.query_items (status filter)."""
    engine.create_item(title="in-queue")  # default status == queue
    resp = client.get("/api/items", params={"status": "done"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # nothing is 'done' -> empty, proving the filter reached the engine
    assert body["items"] == []
    assert body["total"] == 0


def test_items_oversized_limit_is_clamped(client):
    """DoS guard: ?limit=999999 is clamped to <=200 at the HTTP edge (G5 fix).

    The echoed `limit` in the envelope must be clamped, and the engine must
    never be asked to materialize more than 200 rows.
    """
    for _ in range(3):
        engine.create_item(title="x")
    resp = client.get("/api/items", params={"limit": 999999})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["limit"] <= 200, f"limit must be clamped to <=200, got {body['limit']}"
    assert len(body["items"]) <= 200


def test_items_negative_limit_does_not_explode(client):
    """DoS guard: ?limit=-1 is floored to 1 (never passed negative to the engine)."""
    engine.create_item(title="y")
    resp = client.get("/api/items", params={"limit": -1, "offset": -5})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["limit"] >= 1, f"limit must be floored to >=1, got {body['limit']}"
    assert body["offset"] >= 0, f"offset must be floored to >=0, got {body['offset']}"


# ---------------------------------------------------------------------------
# 2. GET /api/items/{id} — present (detail) + absent (404 NOT_FOUND)
# ---------------------------------------------------------------------------
def test_item_detail_returns_item_with_children_notes_deps(client):
    """Criterion: detail endpoint composes item + children + notes + deps."""
    parent = engine.create_item(title="parent")
    engine.create_item(title="child", parent_id=parent["id"])
    resp = client.get(f"/api/items/{parent['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == parent["id"]
    # CONTRACT: detail composes these keys (get_context + get_notes + get_dependencies)
    assert "children" in body
    assert "notes" in body
    assert "dependencies" in body or "deps" in body


def test_item_detail_absent_returns_404_tool_error_not_found(client):
    """Criterion 2: GET /api/items/{absent} -> 404 with ToolError body code NOT_FOUND."""
    absent = str(uuid.uuid4())
    resp = client.get(f"/api/items/{absent}")
    assert resp.status_code == 404, resp.text
    body = resp.json()
    # ToolError.to_dict() shape: {"error": {"code","message","field?"}}
    assert body["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# 3. GET /api/context — dashboard counts/active/blocked
# ---------------------------------------------------------------------------
def test_context_returns_dashboard_counts_active_blocked(client):
    """Criterion 3: GET /api/context -> 200 with counts (dict) + active + blocked."""
    engine.create_item(title="x")
    resp = client.get("/api/context")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body.get("counts"), dict), "counts must be a dict"
    assert "active" in body
    assert "blocked" in body


# ---------------------------------------------------------------------------
# 4. GET /api/sessions — lists the registered session triple
# ---------------------------------------------------------------------------
def test_sessions_lists_registered_session_triple(client):
    """Criterion 4: after presence_register -> session appears with hostname/agent_id/session_id."""
    reg = engine.presence_register(
        hostname="h-test", pid=4242, cli="kiro-cli", theme=""
    )
    sid = reg["session_id"]
    resp = client.get("/api/sessions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # CONTRACT: sessions endpoint returns a list (or {"sessions":[...]}) of presence_list dicts.
    sessions = (
        body["sessions"] if isinstance(body, dict) and "sessions" in body else body
    )
    assert isinstance(sessions, list)
    triples = {
        (s.get("hostname"), s.get("agent_id"), s.get("session_id")) for s in sessions
    }
    assert any(sid == t[2] and t[0] == "h-test" for t in triples), (
        "registered session triple must be listed"
    )


def test_sessions_hostname_filter_is_honored(client):
    """R9: host filter passes through to presence_list."""
    engine.presence_register(hostname="host-a", pid=1, cli="c", theme="")
    engine.presence_register(hostname="host-b", pid=2, cli="c", theme="")
    resp = client.get("/api/sessions", params={"hostname": "host-a"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sessions = (
        body["sessions"] if isinstance(body, dict) and "sessions" in body else body
    )
    assert all(s.get("hostname") == "host-a" for s in sessions)


# ---------------------------------------------------------------------------
# 5. GET /api/arcs — items tagged 'arc'
# ---------------------------------------------------------------------------
def test_arcs_returns_items_tagged_arc(client):
    """Criterion 5: create an item with tags='arc' -> /api/arcs returns it."""
    arc = engine.create_item(title="ARC: big thing", tags="arc")
    engine.create_item(title="plain task")  # not an arc
    resp = client.get("/api/arcs")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    ids = {it["id"] for it in items}
    assert arc["id"] in ids
    for it in items:
        assert "arc" in (it.get("tags") or ""), (
            "arcs endpoint must only return arc-tagged items"
        )


# ---------------------------------------------------------------------------
# 6. PATCH /api/items/{id}/advance — valid 'start' advances; invalid trigger errors
# ---------------------------------------------------------------------------
def test_advance_start_moves_item_to_work(client):
    """Criterion: PATCH advance {trigger:start} -> 200, status becomes 'work'."""
    item = engine.create_item(title="to advance")  # status queue
    resp = client.patch(f"/api/items/{item['id']}/advance", json={"trigger": "start"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # CONTRACT: response reflects the new status somewhere ('status' or nested 'item.status').
    new_status = body.get("status") or (body.get("item") or {}).get("status")
    assert new_status == "work", f"expected work, got {new_status} / body={body}"


def test_advance_invalid_trigger_maps_to_400_or_409(client):
    """Criterion 5: invalid trigger -> ToolError mapped (VALIDATION->400 or CONFLICT->409)."""
    item = engine.create_item(title="bad advance")
    resp = client.patch(f"/api/items/{item['id']}/advance", json={"trigger": "warp"})
    assert resp.status_code in (400, 409), resp.text
    body = resp.json()
    assert body["error"]["code"] in ("VALIDATION", "CONFLICT")


# ---------------------------------------------------------------------------
# 7. POST /api/claims — claim, then a DIFFERENT session on same item -> 409 CONFLICT
# ---------------------------------------------------------------------------
def test_claim_then_distinct_session_conflicts_409(client):
    """Criterion 6: one actor claims a work_item; a second distinct session -> 409 CONFLICT."""
    item = engine.create_item(title="claimable")
    s1 = engine.presence_register(hostname="h1", pid=11, cli="c", theme="")[
        "session_id"
    ]
    s2 = engine.presence_register(hostname="h2", pid=22, cli="c", theme="")[
        "session_id"
    ]

    # First claim via the API succeeds.
    # CONTRACT: POST /api/claims body = {subject_type, subject_ref, session_id}
    r1 = client.post(
        "/api/claims",
        json={"subject_type": "work_item", "subject_ref": item["id"], "session_id": s1},
    )
    assert r1.status_code in (200, 201), r1.text

    # Second, distinct session claiming the SAME item -> CONFLICT.
    r2 = client.post(
        "/api/claims",
        json={"subject_type": "work_item", "subject_ref": item["id"], "session_id": s2},
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "CONFLICT"


# ---------------------------------------------------------------------------
# 8. ToolError mapping — advance on absent item -> 404 (mapping holds across endpoints)
# ---------------------------------------------------------------------------
def test_advance_absent_item_maps_to_404(client):
    """Criterion 7: ToolError NOT_FOUND -> 404 regardless of endpoint."""
    absent = str(uuid.uuid4())
    resp = client.patch(f"/api/items/{absent}/advance", json={"trigger": "start"})
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# 9. CORS — preflight from the dev origin is allowed (SPEC R6)
# ---------------------------------------------------------------------------
def test_cors_preflight_from_dev_origin_allows_origin(client):
    """Criterion 8: OPTIONS preflight from http://localhost:5173 -> Access-Control-Allow-Origin set."""
    resp = client.options(
        "/api/items",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Starlette CORSMiddleware answers preflight with 200.
    assert resp.status_code == 200, resp.text
    allow = resp.headers.get("access-control-allow-origin")
    assert allow in ("http://localhost:5173", "*"), (
        f"missing/invalid CORS allow-origin: {allow!r}"
    )


# ---------------------------------------------------------------------------
# 10. GET /api/metrics + GET /api/workspaces -> 200
# ---------------------------------------------------------------------------
def test_metrics_returns_200_dict(client):
    """Criterion 10: /api/metrics -> 200 with a metrics dict."""
    resp = client.get("/api/metrics")
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), dict)


def test_workspaces_returns_200(client):
    """Criterion 10: /api/workspaces -> 200."""
    resp = client.get("/api/workspaces")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # CONTRACT: list of workspaces (bare list or {"workspaces":[...]}).
    assert isinstance(body, (list, dict))
