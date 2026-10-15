from datetime import datetime, timezone, timedelta

from ..db import get_connection
from ..schemas import check_gate
from .base import (
    ToolError,
    TERMINAL,
    TRANSITIONS,
    PRIORITY_ORDER,
    _now,
    _parse_dt,
    _row_to_dict,
    _workspace_tag_filter,
)
from .transitions import _get_unsatisfied_blockers
from .items import get_ancestors


def _get_items_by_due_date(conn, mode: str, now_dt: datetime) -> list[dict]:
    """Get items by due date. mode: 'due_soon' (next 24h) or 'overdue' (past due)."""
    now_iso = now_dt.isoformat()
    if mode == "due_soon":
        cutoff = (now_dt + timedelta(hours=24)).isoformat()
        rows = conn.execute(
            "SELECT * FROM work_items WHERE due_at IS NOT NULL AND due_at > ? AND due_at <= ? AND status NOT IN ('done','cancelled')",
            (now_iso, cutoff),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM work_items WHERE due_at IS NOT NULL AND due_at <= ? AND status NOT IN ('done','cancelled')",
            (now_iso,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _get_scheduled_upcoming(conn, now_dt: datetime) -> list[dict]:
    """Items with next_run_at within next 24h."""
    cutoff = (now_dt + timedelta(hours=24)).isoformat()
    rows = conn.execute(
        "SELECT * FROM work_items WHERE next_run_at IS NOT NULL AND next_run_at <= ?",
        (cutoff,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_next_item(workspace: str | None = None) -> dict | None:
    conn = get_connection()
    try:
        ws_clause, ws_params = _workspace_tag_filter(workspace)
        where = "WHERE status IN ('queue','work')"
        if ws_clause:
            where += f" AND {ws_clause}"
        rows = conn.execute(
            f"SELECT * FROM work_items {where} ORDER BY status ASC, created_at ASC",
            ws_params,
        ).fetchall()
        now_iso = _now()
        candidates = []
        for r in rows:
            blockers = _get_unsatisfied_blockers(conn, r["id"])
            if not blockers:
                item = _row_to_dict(r)
                # Skip scheduled items whose next_run_at is in the future
                if item.get("next_run_at") and item["next_run_at"] > now_iso:
                    continue
                candidates.append(item)

        def _sort_key(x):
            overdue = 1
            if x.get("due_at") and x["due_at"] <= now_iso:
                overdue = 0
            return (
                overdue,
                0 if x["status"] == "work" else 1,
                PRIORITY_ORDER.get(x["priority"], 2),
            )

        candidates.sort(key=_sort_key)
        return candidates[0] if candidates else None
    finally:
        conn.close()


def get_blocked_items(workspace: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        ws_filter, ws_params = _workspace_tag_filter(workspace)
        ws_and = f" AND {ws_filter}" if ws_filter else ""
        rows = conn.execute(
            f"SELECT * FROM work_items WHERE status='blocked'{ws_and}", ws_params
        ).fetchall()
        result = [_row_to_dict(r) for r in rows]
        # Also find queue items with unsatisfied deps
        queue_rows = conn.execute(
            f"SELECT * FROM work_items WHERE status='queue'{ws_and}", ws_params
        ).fetchall()
        for r in queue_rows:
            blockers = _get_unsatisfied_blockers(conn, r["id"])
            if blockers:
                item = _row_to_dict(r)
                item["blocked_by"] = [_row_to_dict(b) for b in blockers]
                result.append(item)
        return result
    finally:
        conn.close()


def get_context(
    item_id: str | None = None,
    include_ancestors: bool = False,
    workspace: str | None = None,
    include_archived: bool = False,
) -> dict:
    conn = get_connection()
    try:
        if item_id:
            row = conn.execute(
                "SELECT * FROM work_items WHERE id=?", (item_id,)
            ).fetchone()
            if not row:
                raise ToolError("NOT_FOUND", f"Item {item_id} not found", "item_id")
            item = _row_to_dict(row)
            children = [
                _row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM work_items WHERE parent_id=?", (item_id,)
                ).fetchall()
            ]
            notes = [
                _row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM notes WHERE item_id=?", (item_id,)
                ).fetchall()
            ]
            blockers = _get_unsatisfied_blockers(conn, item_id)
            result = {
                "item": item,
                "children": children,
                "notes": notes,
                "blockers": [_row_to_dict(b) for b in blockers],
                "can_advance": len(blockers) == 0 and item["status"] not in TERMINAL,
            }
            if include_ancestors:
                result["ancestors"] = get_ancestors(item_id)
            # Add gate info if schema exists
            if result["can_advance"]:
                next_trigger = "start"
                next_status = TRANSITIONS.get(next_trigger, {}).get(item["status"])
                if next_status:
                    gate = check_gate(item, notes, next_status)
                    result["can_advance"] = gate["can_advance"]
                    result["missing_notes"] = gate["missing"]
                    result["guidance"] = gate["guidance"]
            return result
        # Global context
        ws_clause, ws_params = _workspace_tag_filter(workspace)
        ws_and = f"AND {ws_clause}" if ws_clause else ""

        # Combine workspace + archived filters for WHERE clause
        clauses = []
        if ws_clause:
            clauses.append(ws_clause)
        if not include_archived:
            clauses.append("status != 'archived'")
        combined_where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        counts = {}
        for row in conn.execute(
            f"SELECT status, COUNT(*) as cnt FROM work_items {combined_where} GROUP BY status",
            ws_params,
        ).fetchall():
            counts[row["status"]] = row["cnt"]
        active = [
            _row_to_dict(r)
            for r in conn.execute(
                f"SELECT * FROM work_items WHERE status IN ('work','review') {ws_and} ORDER BY updated_at DESC LIMIT 10",
                ws_params,
            ).fetchall()
        ]
        recent = [
            _row_to_dict(r)
            for r in conn.execute(
                f"SELECT * FROM work_items WHERE status IN ('done','cancelled') {ws_and} ORDER BY updated_at DESC LIMIT 5",
                ws_params,
            ).fetchall()
        ]
        blocked = get_blocked_items(workspace=workspace)
        next_item = get_next_item(workspace=workspace)
        # Stale item detection
        now_dt = datetime.now(timezone.utc)
        stale_items = []
        for row in conn.execute(
            f"SELECT * FROM work_items WHERE status IN ('queue','work') {ws_and}",
            ws_params,
        ).fetchall():
            item = _row_to_dict(row)
            updated = _parse_dt(item["updated_at"])
            days = (now_dt - updated).days
            if (item["status"] == "queue" and days > 7) or (
                item["status"] == "work" and days > 3
            ):
                item["stale_days"] = days
                stale_items.append(item)
        return {
            "counts": counts,
            "active": active,
            "blocked": blocked,
            "recent_completed": recent,
            "next_item": next_item,
            "stale_items": stale_items,
            "due_soon": _get_items_by_due_date(conn, "due_soon", now_dt),
            "overdue": _get_items_by_due_date(conn, "overdue", now_dt),
            "scheduled_upcoming": _get_scheduled_upcoming(conn, now_dt),
        }
    finally:
        conn.close()