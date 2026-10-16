"""RED tests for the session-registry sub-domain (central presence + unified claim).

Orc 1.4.0 — implements ADR-002 + ADR-005. SPEC: docs/specs/SPEC-session-registry.md (R1-R15).

These tests SHOULD FAIL today because engine/presence.py and engine/claims.py do not exist
yet. They will pass after G4.

RED DESIGN (honest, non-aborting collection):
- We import `engine`, `ToolError`, `set_agent_id`, `get_connection` at module top — those ALL
  exist today, so this file COLLECTS cleanly and does NOT break the 177-test baseline.
- The not-yet-existing facade functions (engine.presence_register, engine.claim, ...) are
  accessed as ATTRIBUTES *inside* each test via _fn(). Today that raises AttributeError at the
  call site → genuine RED for the RIGHT reason (the function is absent), one failure per test,
  WITHOUT an ImportError at top-of-module that would abort collection of the whole file.
- We test the PUBLIC contract (engine.X returns dicts with the triple fields / raises ToolError
  with the right code), NOT the internal SQL schema.

Facade function names follow G0 §3 (engine/__init__ re-export) and the SPEC:
    presence_register / presence_heartbeat / presence_end / presence_list / presence_reap
    claim / release / conflicts / get_claim_for
If G4 names a function differently, the fix is a one-line alias here or in the facade — the
behavior assertions are what matter. See orc-sessreg-g3.md for the honesty note on naming.
"""

from datetime import UTC, datetime, timedelta

import pytest

from task_orchestrator import db, engine
from task_orchestrator.engine.base import ToolError, set_agent_id


# --------------------------------------------------------------------------------------------
# Helpers — resolve the not-yet-existing facade functions by attribute (RED = AttributeError).
# --------------------------------------------------------------------------------------------
def _fn(name):
    """Return engine.<name> or fail RED with a clear message if the G4 feature is absent.

    Accessing a missing attribute raises AttributeError, which is the honest RED signal that
    presence.py/claims.py were not implemented yet. Collection is NOT aborted (top-level import
    of `engine` succeeds), so the other 177 tests are unaffected.
    """
    try:
        return getattr(engine, name)
    except AttributeError as exc:
        raise AssertionError(
            f"engine.{name} does not exist yet (G4 not implemented). "
            f"This is the expected RED failure. ({exc})"
        )


def _register(hostname="h", pid=1234, cli="kiro-cli", theme="", agent_id=None):
    """Register a session via the public facade. agent_id is injected via the contextvar
    (mirror of the X-Agent-ID header), exactly as the server boundary would do."""
    set_agent_id(agent_id)
    return _fn("presence_register")(hostname=hostname, pid=pid, cli=cli, theme=theme)


def _make_work_item(title="claim target"):
    """Create a real work_item to be claimed (work_item claims are validated against this)."""
    return engine.create_item(title=title)["id"]


def _age_heartbeat(session_id, seconds_ago):
    """SETUP ONLY (not an assertion of implementation): backdate heartbeat_at directly in the
    DB so we can exercise the lazy-reap cutoff without sleeping 300s. Documented per task rules.
    Uses get_connection() + minimal SQL against the `sessions` table (created by G4)."""
    old = (datetime.now(UTC) - timedelta(seconds=seconds_ago)).isoformat()
    conn = db.get_connection()
    try:
        conn.execute("UPDATE sessions SET heartbeat_at=? WHERE id=?", (old, session_id))
        conn.commit()
    finally:
        conn.close()


def _past_iso(seconds=3600):
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()


# --------------------------------------------------------------------------------------------
# 1. (R3) register returns a session_id and the session is visible in list_active.
# --------------------------------------------------------------------------------------------
def test_register_returns_session_id_and_appears_in_list(engine_db):
    """(R3 / criterion 1) register → non-empty session_id uuid; list_active shows the triple."""
    result = _register(hostname="h1", agent_id="zero")

    assert isinstance(result, dict), "register must return a dict"
    session_id = result.get("session_id")
    assert session_id, "register must return a non-empty session_id"
    assert result.get("hostname") == "h1"
    assert result.get("agent_id") == "zero"

    active = _fn("presence_list")()
    ids = {s["session_id"] for s in active}
    assert session_id in ids, "registered session must appear in list_active"
    mine = next(s for s in active if s["session_id"] == session_id)
    assert mine["hostname"] == "h1"
    assert mine["agent_id"] == "zero"


# --------------------------------------------------------------------------------------------
# 2. (R1 / criterion 2 — THE 6 KIROS) same persona+host → two DISTINCT session_ids.
# --------------------------------------------------------------------------------------------
def test_two_registers_same_persona_same_host_distinct_session_ids(engine_db):
    """(R1) Two registers with agent_id='zero' + hostname='h' → two distinct session_ids.

    Proves the presence KEY is session_id (the process), not the persona — the exact
    DNBSCDC289 case of 6 Kiros all persona 'zero' on one host.
    """
    a = _register(hostname="h", agent_id="zero")
    b = _register(hostname="h", agent_id="zero")

    assert a["session_id"] != b["session_id"], (
        "same persona+host MUST yield distinct session_ids (6-Kiros case)"
    )


# --------------------------------------------------------------------------------------------
# 3. (R8 CRITICAL — anti-rework) different session, same subject → CONFLICT naming A's triple.
# --------------------------------------------------------------------------------------------
def test_claim_conflict_between_two_sessions_same_persona_host(engine_db):
    """(R8) Session A claims work_item X. Session B (same persona+host, distinct session_id)
    claims X → ToolError CONFLICT identifying A's triple.

    This is the test that protects the central ADR-002 anti-rework guarantee: conflict is keyed
    by session_id, so two 'zero' sessions on the same host still conflict. The claim-under-test
    is called DIRECTLY (no try/except swallowing) so RED is honest.
    """
    sess_a = _register(hostname="h", agent_id="zero")
    sess_b = _register(hostname="h", agent_id="zero")
    assert sess_a["session_id"] != sess_b["session_id"]

    item_id = _make_work_item()

    # A claims successfully.
    _fn("claim")(
        subject_type="work_item", subject_ref=item_id, session_id=sess_a["session_id"]
    )

    # B must be refused with a CONFLICT ToolError that names A's triple.
    with pytest.raises(ToolError) as exc_info:
        _fn("claim")(
            subject_type="work_item",
            subject_ref=item_id,
            session_id=sess_b["session_id"],
        )
    err = exc_info.value
    assert err.code == "CONFLICT", f"expected CONFLICT, got {err.code}"
    # The conflict message/payload must identify the holder (session A). Accept the session_id
    # (uuid) appearing in the message, which is the minimal proof the holder is named.
    assert sess_a["session_id"] in str(err.message), (
        "CONFLICT must identify holder A's triple (session_id must appear)"
    )


# --------------------------------------------------------------------------------------------
# 4. (R7) work_item validation vs free-form resource.
# --------------------------------------------------------------------------------------------
def test_claim_work_item_absent_id_not_found(engine_db):
    """(R7) claim(work_item, <absent id>) → NOT_FOUND."""
    sess = _register()
    with pytest.raises(ToolError) as exc_info:
        _fn("claim")(
            subject_type="work_item",
            subject_ref="does-not-exist-0000",
            session_id=sess["session_id"],
        )
    assert exc_info.value.code == "NOT_FOUND"


def test_claim_resource_freeform_accepted(engine_db):
    """(R7) claim(resource, 'any/path') → ok (free-form subject_ref accepted)."""
    sess = _register()
    result = _fn("claim")(
        subject_type="resource",
        subject_ref="src/foo/bar.py",
        session_id=sess["session_id"],
        resource_type="file",
    )
    assert isinstance(result, dict)
    assert result.get("subject_ref") == "src/foo/bar.py"


# --------------------------------------------------------------------------------------------
# 5. (R9) list_active filtered by hostname / agent_id → correct subsets, each with the triple.
# --------------------------------------------------------------------------------------------
def test_list_active_filters_by_hostname_and_agent_id(engine_db):
    """(R9) list_active(hostname=..) and list_active(agent_id=..) return the right subsets."""
    s_h1_zero = _register(hostname="h1", agent_id="zero")
    s_h2_zero = _register(hostname="h2", agent_id="zero")
    s_h1_tpol = _register(hostname="h1", agent_id="tpol")

    by_h1 = _fn("presence_list")(hostname="h1")
    h1_ids = {s["session_id"] for s in by_h1}
    assert s_h1_zero["session_id"] in h1_ids
    assert s_h1_tpol["session_id"] in h1_ids
    assert s_h2_zero["session_id"] not in h1_ids, (
        "h2 session must be excluded by hostname='h1'"
    )

    by_zero = _fn("presence_list")(agent_id="zero")
    zero_ids = {s["session_id"] for s in by_zero}
    assert s_h1_zero["session_id"] in zero_ids
    assert s_h2_zero["session_id"] in zero_ids
    assert s_h1_tpol["session_id"] not in zero_ids, (
        "tpol must be excluded by agent_id='zero'"
    )

    # Each row carries the full triple.
    for s in by_h1:
        assert "session_id" in s and "hostname" in s and "agent_id" in s


# --------------------------------------------------------------------------------------------
# 6. (R10/R11 reap lazy) stale heartbeat → session reaped on list_active AND its claim freed.
# --------------------------------------------------------------------------------------------
def test_stale_session_reaped_lazily_and_claims_cascade(engine_db):
    """(R10/R11) A session with heartbeat_at > 300s is reaped on the next list_active, and its
    claim is cascade-released. Proves lazy reap + CASCADE.

    Setup: register, claim, then backdate heartbeat_at directly (SETUP, documented) to simulate
    a dead session without sleeping. The ASSERTIONS are purely on the public contract afterwards.
    """
    sess = _register(hostname="hdead", agent_id="zero")
    item_id = _make_work_item()
    _fn("claim")(
        subject_type="work_item", subject_ref=item_id, session_id=sess["session_id"]
    )

    _age_heartbeat(sess["session_id"], seconds_ago=400)  # > 300s cutoff (SETUP only)

    active = _fn("presence_list")()  # triggers lazy reap
    ids = {s["session_id"] for s in active}
    assert sess["session_id"] not in ids, (
        "stale session (>300s) must be reaped from list_active"
    )

    # Its claim must be gone → the item is claimable again (no active holder).
    holder = _fn("get_claim_for")(subject_type="work_item", subject_ref=item_id)
    assert holder is None, "dead session's claim must be cascade-released (R10)"


def test_heartbeat_keeps_session_alive(engine_db):
    """(R10/6b) After backdating then heartbeat(session_id), the session is NOT reaped."""
    sess = _register(hostname="halive", agent_id="zero")
    _age_heartbeat(sess["session_id"], seconds_ago=400)  # make it look stale (SETUP)

    _fn("presence_heartbeat")(sess["session_id"])  # refresh heartbeat_at to now

    active = _fn("presence_list")()
    ids = {s["session_id"] for s in active}
    assert sess["session_id"] in ids, "session with fresh heartbeat must survive reap"


# --------------------------------------------------------------------------------------------
# 7. (R13) expired claim is excluded from conflicts()/get_claim_for().
# --------------------------------------------------------------------------------------------
def test_expired_claim_excluded_from_reads(engine_db):
    """(R13) A claim with expires_at in the past does not appear in get_claim_for/conflicts."""
    sess = _register(hostname="h", agent_id="zero")
    item_id = _make_work_item()
    _fn("claim")(
        subject_type="work_item",
        subject_ref=item_id,
        session_id=sess["session_id"],
        expires_at=_past_iso(3600),  # already expired
    )

    holder = _fn("get_claim_for")(subject_type="work_item", subject_ref=item_id)
    assert holder is None, "expired claim must be excluded from get_claim_for (R13)"

    other = _register(hostname="h", agent_id="zero")
    conflicting = _fn("conflicts")(
        subjects=[("work_item", item_id)], session_id=other["session_id"]
    )
    assert conflicting == [] or all(
        c.get("subject_ref") != item_id for c in conflicting
    ), "expired claim must not surface as a conflict (R13)"


# --------------------------------------------------------------------------------------------
# 8. (R15) end(session_id) → session gone + its claims cascade-deleted.
# --------------------------------------------------------------------------------------------
def test_end_session_cascades_claims(engine_db):
    """(R15) agent_end deletes the session and cascade-deletes its claims."""
    sess = _register(hostname="h", agent_id="zero")
    item_id = _make_work_item()
    _fn("claim")(
        subject_type="work_item", subject_ref=item_id, session_id=sess["session_id"]
    )

    _fn("presence_end")(sess["session_id"])

    active = _fn("presence_list")()
    ids = {s["session_id"] for s in active}
    assert sess["session_id"] not in ids, "ended session must disappear"

    holder = _fn("get_claim_for")(subject_type="work_item", subject_ref=item_id)
    assert holder is None, "ended session's claims must cascade-delete (R15)"


# --------------------------------------------------------------------------------------------
# 9. (R12) get_context on a claimed item includes the owner's triple.
#    HONESTY NOTE: wiring get_context to expose active_claim is G4 work (SPEC §6). We assert the
#    STABLE engine-level contract (get_claim_for returns the owner's triple) AS THE PRIMARY
#    proof, and additionally probe get_context for active_claim — both are G4-dependent, so both
#    are RED today. If G4 ships get_claim_for but defers the get_context wiring, split this test.
# --------------------------------------------------------------------------------------------
def test_get_claim_for_returns_owner_triple(engine_db):
    """(R12, stable level) After A claims item, get_claim_for returns A's triple."""
    sess = _register(hostname="hc", agent_id="zero", cli="kiro-cli")
    item_id = _make_work_item()
    _fn("claim")(
        subject_type="work_item", subject_ref=item_id, session_id=sess["session_id"]
    )

    holder = _fn("get_claim_for")(subject_type="work_item", subject_ref=item_id)
    assert holder is not None, "active claim must be returned by get_claim_for"
    assert holder["session_id"] == sess["session_id"]
    assert holder["hostname"] == "hc"
    assert holder["agent_id"] == "zero"


def test_get_context_includes_active_claim(engine_db):
    """(R12, wiring level — G4 get_context plug) get_context(item) exposes active_claim triple.

    Depends on the G4 wiring of queries.get_context (SPEC §6). RED today because the claim
    facade does not exist; if G4 implements get_claim_for but defers this wiring, this test
    stays RED and flags the missing plug — that is intentional, not a false negative.
    """
    sess = _register(hostname="hc", agent_id="zero")
    item_id = _make_work_item()
    _fn("claim")(
        subject_type="work_item", subject_ref=item_id, session_id=sess["session_id"]
    )

    ctx = engine.get_context(item_id)
    # Find the item payload in the context (get_context returns a dict around the item).
    active_claim = None
    if isinstance(ctx, dict):
        if "active_claim" in ctx:
            active_claim = ctx["active_claim"]
        elif isinstance(ctx.get("item"), dict):
            active_claim = ctx["item"].get("active_claim")
    assert active_claim is not None, (
        "get_context must include active_claim with the owner's triple (R12, G4 wiring)"
    )
    assert active_claim.get("session_id") == sess["session_id"]
