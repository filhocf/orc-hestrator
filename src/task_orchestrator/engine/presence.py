"""Central presence sub-domain (session registry) — Orc 1.4.0 (ADR-002).

Actor identity is the triple (hostname, agent_id, session_id). session_id (uuid) is the
global presence/claim key; hostname and agent_id are always carried for display/query.

Follows the engine/notes.py pattern: free functions over get_connection(), importing
helpers from .base, with explicit commit()/close() in finally.
"""

from datetime import UTC, datetime, timedelta

from ..db import get_connection
from .base import _now, _row_to_dict, _uid, get_agent_id

# Heartbeat older than this (seconds) → the session is dead and reaped (R10).
HEARTBEAT_TIMEOUT_SECONDS = 300


def _label(hostname: str, agent_id: str | None, session_id: str) -> str:
    """Human-readable triple label: hostname/agent_id/session_short (G0 §0)."""
    short = session_id[:8] if session_id else ""
    return f"{hostname}/{agent_id or '(anon)'}/sess-{short}"


def _cutoff_iso() -> str:
    return (
        datetime.now(UTC) - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
    ).isoformat()


def _reap_stale(conn) -> int:
    """Delete sessions whose heartbeat_at is older than the cutoff. Claims cascade.

    Uses the caller's connection (foreign_keys=ON → CASCADE cleans claims). Caller commits.
    """
    cutoff = _cutoff_iso()
    dead = conn.execute(
        "SELECT id FROM sessions WHERE heartbeat_at < ?", (cutoff,)
    ).fetchall()
    if not dead:
        return 0
    conn.execute("DELETE FROM sessions WHERE heartbeat_at < ?", (cutoff,))
    return len(dead)


def register(hostname: str, pid: int = 0, cli: str = "", theme: str = "") -> dict:
    """Register a session. Generates session_id (uuid); agent_id from contextvar.

    hostname arrives already resolved (arg → X-Client-Hostname header → 'unknown') at the
    server boundary — at engine level it is an argument (mirror of agent_id handling).
    Returns the triple + label.
    """
    conn = get_connection()
    try:
        session_id = _uid()
        agent_id = get_agent_id()
        host = hostname or "unknown"
        now = _now()
        conn.execute(
            "INSERT INTO sessions (id, agent_id, hostname, pid, cli, theme, status, started_at, heartbeat_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (session_id, agent_id, host, pid, cli, theme, "active", now, now),
        )
        conn.commit()
        return {
            "session_id": session_id,
            "agent_id": agent_id,
            "hostname": host,
            "cli": cli,
            "theme": theme,
            "label": _label(host, agent_id, session_id),
        }
    finally:
        conn.close()


def heartbeat(session_id: str) -> bool:
    """Refresh heartbeat_at (server clock) and mark active. Returns True if the session exists."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE sessions SET heartbeat_at=?, status='active' WHERE id=?",
            (_now(), session_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def end(session_id: str) -> bool:
    """Delete the session; its claims cascade-delete (FK ON DELETE CASCADE). Returns True if removed."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_active(hostname: str | None = None, agent_id: str | None = None) -> list[dict]:
    """List active sessions, lazily reaping stale ones first (R11). Optional triple filters (R9)."""
    conn = get_connection()
    try:
        _reap_stale(conn)
        conn.commit()
        where = ["status != 'dead'"]
        params: list = []
        if hostname:
            where.append("hostname = ?")
            params.append(hostname)
        if agent_id:
            where.append("agent_id = ?")
            params.append(agent_id)
        clause = " AND ".join(where)
        rows = conn.execute(
            f"SELECT * FROM sessions WHERE {clause} ORDER BY started_at DESC", params
        ).fetchall()
        result = []
        for r in rows:
            d = _row_to_dict(r)
            d["session_id"] = d.pop("id")
            d["label"] = _label(d["hostname"], d.get("agent_id"), d["session_id"])
            result.append(d)
        return result
    finally:
        conn.close()


def reap(timeout_s: int = HEARTBEAT_TIMEOUT_SECONDS) -> int:
    """Explicitly reap stale sessions (admin/tool). Claims cascade. Returns count reaped."""
    conn = get_connection()
    try:
        cutoff = (datetime.now(UTC) - timedelta(seconds=timeout_s)).isoformat()
        dead = conn.execute(
            "SELECT id FROM sessions WHERE heartbeat_at < ?", (cutoff,)
        ).fetchall()
        if not dead:
            return 0
        conn.execute("DELETE FROM sessions WHERE heartbeat_at < ?", (cutoff,))
        conn.commit()
        return len(dead)
    finally:
        conn.close()
