from datetime import UTC, datetime, timedelta

from ..db import get_connection
from ..schemas import check_gate
from .base import (
    PRIORITY_ORDER,
    TERMINAL,
    TRANSITIONS,
    ToolError,
    _now,
    _parse_dt,
    _row_to_dict,
    _workspace_tag_filter,
)
from .items import get_ancestors
from .transitions import _get_unsatisfied_blockers


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
        if not candidates:
            return None
        chosen = candidates[0]
        # R12: attach the active claim (owner's triple) to the returned item only.
        from .claims import get_claim_for

        active_claim = get_claim_for("work_item", chosen["id"])
        if active_claim is not None:
            chosen["active_claim"] = active_claim
        return chosen
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


VERBOSITY_LEVELS = {"compact", "standard", "full"}
STALE_LIMIT = 10  # R-B4: truncamento visível via stale_total/stale_limit
STANDARD_DESCRIPTION = 200

# A regra é expressa em DIAS INTEIROS: `(now - updated).days > 7` só é verdade a
# partir de 8 dias completos. Traduzir para `updated_at < now - 7d` incluía
# "7 dias e 1 segundo" (days == 7), que a regra original não considera stale.
# Daí o corte em 8 e 4 dias, com `<=`: delta >= N dias  <=>  updated_at <= now - N dias.
QUEUE_STALE_DAYS = 8
WORK_STALE_DAYS = 4


def _short_id(item: dict) -> str:
    """R-B3: 8 chars bastam (resolve_short_id aceita 4+); 36 estoura o teto do AC-B1."""
    return (item.get("id") or "")[:8]


def _compact_row(item: dict) -> list:
    return [
        _short_id(item),
        item.get("title"),
        item.get("status"),
        item.get("priority"),
        item.get("stale_days"),
    ]


def _standard_row(item: dict) -> dict:
    description = item.get("description") or ""
    if len(description) > STANDARD_DESCRIPTION:
        # O teto de 200 inclui a reticência, não vem antes dela.
        description = description[: STANDARD_DESCRIPTION - 3] + "..."
    return {
        "id": _short_id(item),
        "title": item.get("title"),
        "status": item.get("status"),
        "priority": item.get("priority"),
        "stale_days": item.get("stale_days"),
        "description": description,
    }


def get_context(
    item_id: str | None = None,
    include_ancestors: bool = False,
    workspace: str | None = None,
    include_archived: bool = False,
    verbosity: str = "full",
) -> dict:
    if verbosity not in VERBOSITY_LEVELS:
        raise ToolError(
            "VALIDATION",
            f"verbosity must be one of {sorted(VERBOSITY_LEVELS)}, got {verbosity!r}",
            "verbosity",
        )
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
            # R12: expose the active claim (owner's triple) on the returned item.
            from .claims import get_claim_for

            active_claim = get_claim_for("work_item", item_id)
            if active_claim is not None:
                item["active_claim"] = active_claim
            result = {
                "item": item,
                "children": children,
                "notes": notes,
                "blockers": [_row_to_dict(b) for b in blockers],
                "can_advance": len(blockers) == 0 and item["status"] not in TERMINAL,
            }
            if active_claim is not None:
                result["active_claim"] = active_claim
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
        now_dt = datetime.now(UTC)
        if verbosity == "full":
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

        # compact / standard (R-B3..R-B5): o limite de staleness é do SQL, não do
        # Python — materializar toda a fila para filtrar era o custo do D1.
        queue_cutoff = (now_dt - timedelta(days=QUEUE_STALE_DAYS)).isoformat()
        work_cutoff = (now_dt - timedelta(days=WORK_STALE_DAYS)).isoformat()
        stale_clause = "((status='queue' AND updated_at <= ?) OR (status='work' AND updated_at <= ?))"

        stale_total = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM work_items WHERE {stale_clause} {ws_and}",
            [queue_cutoff, work_cutoff] + ws_params,
        ).fetchone()["cnt"]
        stale_rows = conn.execute(
            f"SELECT * FROM work_items WHERE {stale_clause} {ws_and} "
            "ORDER BY updated_at ASC LIMIT ?",
            [queue_cutoff, work_cutoff] + ws_params + [STALE_LIMIT],
        ).fetchall()
        stale_items = []
        for row in stale_rows:
            item = _row_to_dict(row)
            item["stale_days"] = (now_dt - _parse_dt(item["updated_at"])).days
            stale_items.append(item)

        row_fn = _standard_row if verbosity == "standard" else _compact_row
        return {
            "counts": counts,
            "next_item": (
                {
                    "id": _short_id(next_item),
                    "title": next_item.get("title"),
                    "priority": next_item.get("priority"),
                }
                if next_item
                else None
            ),
            "active": [row_fn(item) for item in active],
            "blocked": [_compact_row(item) for item in blocked],
            "stale": [_compact_row(item) for item in stale_items],
            "stale_total": stale_total,
            "stale_limit": STALE_LIMIT,
        }
    finally:
        conn.close()
