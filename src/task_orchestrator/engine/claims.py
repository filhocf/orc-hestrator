"""Unified claim sub-domain — Orc 1.4.0 (ADR-002).

One claims table covers work_item and resource subjects. The owner is a session_id (the
process), so two DIFFERENT sessions on the same subject conflict — even same persona+host
(R8 anti-rework guarantee). The owner's triple is obtained by JOIN on sessions.

Leaf-ish domain: reads work_items (for validation) and sessions (for the triple JOIN); does
NOT import queries — queries aggregates this via get_claim_for (avoids the import cycle).
"""

from ..db import get_connection
from .base import _now, _uid, get_agent_id
from .presence import _label, _reap_stale

VALID_SUBJECT_TYPES = {"work_item", "resource"}


def _is_expired(expires_at: str | None, now_iso: str) -> bool:
    return bool(expires_at) and expires_at <= now_iso


def _active_claim_row(conn, subject_type: str, subject_ref: str, now_iso: str):
    """Return the non-expired claim row (joined with its owner session) or None."""
    row = conn.execute(
        """
        SELECT c.*, s.hostname AS s_hostname, s.agent_id AS s_agent_id, s.cli AS s_cli
        FROM claims c
        JOIN sessions s ON c.session_id = s.id
        WHERE c.subject_type=? AND c.subject_ref=?
        """,
        (subject_type, subject_ref),
    ).fetchone()
    if row is None:
        return None
    if _is_expired(row["expires_at"], now_iso):
        return None
    return row


def _owner_triple(row) -> dict:
    """Build the owner triple dict from a joined claim row."""
    return {
        "session_id": row["session_id"],
        "agent_id": row["s_agent_id"],
        "hostname": row["s_hostname"],
        "cli": row["s_cli"],
        "label": _label(row["s_hostname"], row["s_agent_id"], row["session_id"]),
        "claimed_at": row["claimed_at"],
        "expires_at": row["expires_at"],
        "subject_type": row["subject_type"],
        "subject_ref": row["subject_ref"],
        "resource_type": row["resource_type"],
    }


def claim(
    subject_type: str,
    subject_ref: str,
    session_id: str,
    resource_type: str | None = None,
    expires_at: str | None = None,
) -> dict:
    """Claim a work_item (validated against work_items.id) or a free-form resource.

    Conflict is keyed by session_id: a non-expired claim held by a DIFFERENT session_id on the
    same (subject_type, subject_ref) raises CONFLICT naming the holder's triple (R8). The
    conflict is DETECTED before any write — never a blind INSERT OR REPLACE that masks it.
    """
    from .base import ToolError

    conn = get_connection()
    try:
        if subject_type not in VALID_SUBJECT_TYPES:
            raise ToolError(
                "VALIDATION",
                f"Invalid subject_type: {subject_type}. Valid: {sorted(VALID_SUBJECT_TYPES)}",
                "subject_type",
            )
        # Owner session must exist.
        if not conn.execute(
            "SELECT 1 FROM sessions WHERE id=?", (session_id,)
        ).fetchone():
            raise ToolError(
                "NOT_FOUND", f"Session {session_id} not found", "session_id"
            )
        # work_item subjects are validated against work_items; resource is free-form.
        if (
            subject_type == "work_item"
            and not conn.execute(
                "SELECT 1 FROM work_items WHERE id=?", (subject_ref,)
            ).fetchone()
        ):
            raise ToolError(
                "NOT_FOUND", f"Work item {subject_ref} not found", "subject_ref"
            )

        now_iso = _now()
        existing = _active_claim_row(conn, subject_type, subject_ref, now_iso)
        if existing is not None and existing["session_id"] != session_id:
            holder = _owner_triple(existing)
            raise ToolError(
                "CONFLICT",
                f"{subject_type} {subject_ref} is already claimed by "
                f"{holder['label']} (session_id={holder['session_id']}, "
                f"agent_id={holder['agent_id']}, hostname={holder['hostname']})",
                "subject_ref",
            )

        agent_id = get_agent_id()
        # Same-owner re-claim or an expired/absent claim → (re)write respecting the UNIQUE index.
        conn.execute(
            "INSERT OR REPLACE INTO claims "
            "(id, subject_type, subject_ref, session_id, agent_id, resource_type, claimed_at, expires_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                _uid(),
                subject_type,
                subject_ref,
                session_id,
                agent_id,
                resource_type,
                now_iso,
                expires_at,
            ),
        )
        conn.commit()
        return {
            "subject_type": subject_type,
            "subject_ref": subject_ref,
            "session_id": session_id,
            "agent_id": agent_id,
            "resource_type": resource_type,
            "claimed_at": now_iso,
            "expires_at": expires_at,
        }
    finally:
        conn.close()


def release(session_id: str, subject_type: str, subject_ref: str) -> bool:
    """Release a claim held by session_id on the subject. Returns True if a row was removed."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM claims WHERE session_id=? AND subject_type=? AND subject_ref=?",
            (session_id, subject_type, subject_ref),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def conflicts(session_id: str, subjects: list[tuple[str, str]]) -> list[dict]:
    """Return the owner triple for each given subject claimed by ANOTHER session (non-expired).

    Lazily reaps stale sessions first (R11); excludes expired claims (R13).
    """
    conn = get_connection()
    try:
        _reap_stale(conn)
        conn.commit()
        if not subjects:
            return []
        now_iso = _now()
        result = []
        for subject_type, subject_ref in subjects:
            row = _active_claim_row(conn, subject_type, subject_ref, now_iso)
            if row is not None and row["session_id"] != session_id:
                result.append(_owner_triple(row))
        return result
    finally:
        conn.close()


def get_claim_for(subject_type: str, subject_ref: str) -> dict | None:
    """Return the owner triple of the active claim on a subject, or None if absent/expired.

    Lazily reaps stale sessions first (R11); excludes expired claims (R13).
    """
    conn = get_connection()
    try:
        _reap_stale(conn)
        conn.commit()
        now_iso = _now()
        row = _active_claim_row(conn, subject_type, subject_ref, now_iso)
        return _owner_triple(row) if row is not None else None
    finally:
        conn.close()
