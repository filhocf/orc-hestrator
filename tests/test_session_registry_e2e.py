"""E2E boundary tests for the session-registry tools (Orc 1.4.0).

Closes the 1.4.0 E2E gap: the engine (presence/claims) already has unit+integration
coverage, but the *tools* in server.py — which resolve the X-Agent-ID / X-Client-Hostname
HTTP headers at the boundary and feed the engine via the agent_id contextvar — had NO test.

These tests are GREEN by design: the feature is implemented and passing. They prove the
end-to-end contract header → boundary resolution → engine → DB.

APPROACH (honest note):
    Spinning up the full streamable-http stream + MCP initialize/session handshake just to
    exercise call_tool is fragile (test_oauth_auth.py deliberately only checks the 401 on a
    GET, it never does a call_tool). So instead of faking the transport we inject the ONE
    thing the real boundary reads: the FastMCP request context.

    We patch `server.mcp.get_context` to return a context whose
    `.request_context.request.headers` is a real dict of the HTTP headers. Everything else is
    REAL: the production `_resolve_agent_id` / `_resolve_hostname` functions run their real
    precedence logic, the real `@with_agent_id` decorator sets/resets the contextvar, the real
    tool functions call the real engine, and the real engine writes to the (temp) SQLite DB.
    We then read the DB back to assert the stored identity.

    We do NOT mock `_resolve_agent_id` (the existing test_agent_id_boundary.py already does the
    pure-unit version of that). Here the header dict is the input and the DB row is the output
    — that is the E2E contract, not the contextvar internals.
"""

import json
from unittest.mock import Mock, patch

from task_orchestrator import db, server
from task_orchestrator.engine.base import set_agent_id


def _ctx_with_headers(headers: dict):
    """Build a fake FastMCP context carrying the given HTTP request headers.

    Only the transport-layer carrier is faked (we cannot stand up the real stream without a
    fragile MCP handshake). The header values themselves are the real test input that the
    production resolvers read.
    """
    request = Mock()
    request.headers = headers
    ctx = Mock()
    ctx.request_context = Mock()
    ctx.request_context.request = request
    return ctx


def _patch_headers(headers: dict):
    """Patch the boundary so mcp.get_context() exposes `headers` to the resolvers."""
    return patch.object(
        server.mcp, "get_context", return_value=_ctx_with_headers(headers)
    )


def _session_row(session_id: str):
    """Read a stored session straight from the DB (the end of the E2E path)."""
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT agent_id, hostname FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    finally:
        conn.close()
    return row


def _claim_row(subject_ref: str):
    """Read a stored claim straight from the DB."""
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT agent_id, session_id FROM claims WHERE subject_ref=?",
            (subject_ref,),
        ).fetchone()
    finally:
        conn.close()
    return row


# ---------------------------------------------------------------------------------------------
# Case 1 — headers carry the identity; NO args passed. Proves the boundary reads BOTH headers.
# ---------------------------------------------------------------------------------------------
def test_register_resolves_both_headers_into_db(engine_db):
    """E2E: X-Agent-ID + X-Client-Hostname headers → session row with that exact identity.

    Nothing is passed as an argument, so agent_id='zero' and hostname='sirdata' can ONLY have
    come from the headers — through _resolve_agent_id / _resolve_hostname, the contextvar, the
    engine, and into the DB.
    """
    set_agent_id(None)
    headers = {"x-agent-id": "zero", "x-client-hostname": "sirdata"}
    with _patch_headers(headers):
        result = json.loads(server.agent_register())

    assert result["agent_id"] == "zero"
    assert result["hostname"] == "sirdata"

    row = _session_row(result["session_id"])
    assert row is not None, "session must be persisted"
    assert row["agent_id"] == "zero", "agent_id in DB must come from X-Agent-ID header"
    assert row["hostname"] == "sirdata", (
        "hostname in DB must come from X-Client-Hostname header"
    )


# ---------------------------------------------------------------------------------------------
# Case 2 — hostname arg precedence: arg wins when the X-Client-Hostname header is absent.
# ---------------------------------------------------------------------------------------------
def test_register_hostname_arg_takes_precedence_when_header_absent(engine_db):
    """E2E (R5 precedence): _resolve_hostname is arg → header → 'unknown'.

    With the X-Client-Hostname header ABSENT and hostname='h2' passed as an argument, the
    stored hostname must be 'h2' (arg-first). agent_id still comes from the header.
    """
    set_agent_id(None)
    headers = {"x-agent-id": "zero"}  # no x-client-hostname
    with _patch_headers(headers):
        result = json.loads(server.agent_register(hostname="h2"))

    assert result["agent_id"] == "zero"
    assert result["hostname"] == "h2"

    row = _session_row(result["session_id"])
    assert row["hostname"] == "h2", "arg hostname must win when the header is absent"
    assert row["agent_id"] == "zero"


# ---------------------------------------------------------------------------------------------
# Case 2b — no hostname arg AND no header → 'unknown' (the documented final fallback).
# ---------------------------------------------------------------------------------------------
def test_register_hostname_falls_back_to_unknown(engine_db):
    """E2E (R5 fallback): no hostname arg and no header → 'unknown' (NOT the server socket)."""
    set_agent_id(None)
    with _patch_headers({"x-agent-id": "zero"}):
        result = json.loads(server.agent_register())

    assert result["hostname"] == "unknown"
    row = _session_row(result["session_id"])
    assert row["hostname"] == "unknown"


# ---------------------------------------------------------------------------------------------
# Case 3 — claim/conflict (R8) through the TOOL path, identity resolved from the header.
# ---------------------------------------------------------------------------------------------
def test_claim_records_header_identity_and_conflicts_across_sessions(engine_db):
    """E2E (R8): claim via the tool stores the header-resolved agent_id; a DIFFERENT session on
    the same subject CONFLICTs, naming the holder's triple.

    Both registrations carry the SAME header identity (agent_id='zero', hostname='h1') but get
    DISTINCT session_ids — the conflict is keyed by session_id (same persona+host still
    conflicts), which is the anti-rework guarantee.
    """
    set_agent_id(None)
    work_item_id = server.engine.create_item(title="e2e claim target")["id"]

    headers = {"x-agent-id": "zero", "x-client-hostname": "h1"}
    with _patch_headers(headers):
        session_one = json.loads(server.agent_register())["session_id"]
        session_two = json.loads(server.agent_register())["session_id"]

        claim_one = json.loads(
            server.claim(
                subject_type="work_item",
                subject_ref=work_item_id,
                session_id=session_one,
            )
        )
        assert "error" not in claim_one, f"first claim should succeed, got {claim_one}"
        assert claim_one["agent_id"] == "zero", (
            "claim must store the header-resolved agent_id"
        )

        claim_two = json.loads(
            server.claim(
                subject_type="work_item",
                subject_ref=work_item_id,
                session_id=session_two,
            )
        )

    assert session_one != session_two, (
        "each agent_register must mint a distinct session_id"
    )
    # The second claim by a different session must CONFLICT (error envelope: {"error": {...}}).
    conflict = claim_two["error"]
    assert conflict["code"] == "CONFLICT", f"expected CONFLICT, got {claim_two}"
    assert "zero" in conflict["message"], "conflict must name the holder's agent_id"
    assert session_one in conflict["message"], (
        "conflict must name the holder's session_id"
    )

    # The persisted claim must still belong to the first session with the header identity.
    row = _claim_row(work_item_id)
    assert row["agent_id"] == "zero"
    assert row["session_id"] == session_one


# ---------------------------------------------------------------------------------------------
# Case 4 — no X-Agent-ID header → anonymous (agent_id None), operation still succeeds.
# ---------------------------------------------------------------------------------------------
def test_register_anonymous_when_no_agent_id_header(engine_db, monkeypatch):
    """E2E (R4): with no X-Agent-ID header (and no env fallback), agent_id resolves to None and
    the session is still registered (anonymous is a valid identity)."""
    # Ensure the env fallback does not supply an agent_id.
    monkeypatch.delenv("MCP_AGENT_ID", raising=False)
    set_agent_id(None)

    with _patch_headers({"x-client-hostname": "anon-host"}):
        result = json.loads(server.agent_register())

    assert result["agent_id"] is None, (
        "no header + no env must resolve to anonymous (None)"
    )
    assert result["hostname"] == "anon-host"

    row = _session_row(result["session_id"])
    assert row is not None, "anonymous session must still be persisted"
    assert row["agent_id"] is None
    assert row["hostname"] == "anon-host"
