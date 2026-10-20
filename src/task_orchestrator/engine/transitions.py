from datetime import UTC, datetime

from croniter import croniter

from ..db import get_connection
from ..schemas import can_cancel, check_gate, should_skip_review
from .base import TERMINAL, TRANSITIONS, ToolError, _now, _row_to_dict, get_agent_id


def advance_item(item_id: str, trigger: str) -> dict:
    if trigger not in TRANSITIONS and trigger not in ("resume", "hold"):
        raise ToolError(
            "VALIDATION",
            f"Invalid trigger: {trigger}. Valid: {list(TRANSITIONS.keys()) + ['resume', 'hold']}",
            "trigger",
        )
    # hold is alias for block
    if trigger == "hold":
        trigger = "block"
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise ToolError("NOT_FOUND", f"Item {item_id} not found", "item_id")
        current = row["status"]

        if trigger == "resume":
            if current != "blocked":
                raise ToolError(
                    "CONFLICT",
                    f"Can only resume blocked items, current: {current}",
                    "trigger",
                )
            new_status = row["previous_status"] or "work"
        elif trigger == "block":
            if current in TERMINAL or current == "blocked":
                raise ToolError("CONFLICT", f"Cannot block from {current}", "trigger")
            new_status = "blocked"
            conn.execute(
                "UPDATE work_items SET previous_status=? WHERE id=?", (current, item_id)
            )
        else:
            if current not in TRANSITIONS[trigger]:
                raise ToolError(
                    "CONFLICT", f"Cannot {trigger} from {current}", "trigger"
                )
            new_status = TRANSITIONS[trigger][current]

        # Check dependencies for advancing triggers
        if trigger in ("start", "complete") and current == "queue":
            blockers = _get_unsatisfied_blockers(conn, item_id)
            if blockers:
                titles = [b["title"] for b in blockers]
                raise ToolError(
                    "DEPENDENCY_UNSATISFIED",
                    f"Blocked by unfinished items: {', '.join(titles)}",
                    "item_id",
                )

        # Check note schema gates
        if trigger in ("start", "complete"):
            item_dict = _row_to_dict(row)
            notes = [
                _row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM notes WHERE item_id=?", (item_id,)
                ).fetchall()
            ]
            gate = check_gate(item_dict, notes, new_status)
            if not gate["can_advance"]:
                missing_keys = [m["key"] for m in gate["missing"]]
                raise ToolError(
                    "GATE_BLOCKED",
                    f"Missing required notes: {', '.join(missing_keys)}"
                    + (f". Hint: {gate['guidance']}" if gate["guidance"] else ""),
                    "item_id",
                )

        # Check cancel permission (permanent lifecycle)
        if trigger == "cancel" and not can_cancel(_row_to_dict(row)):
            raise ToolError(
                "CONFLICT", "Cannot cancel: item has permanent lifecycle", "trigger"
            )

        # Auto-skip review for 'auto' lifecycle
        if (
            trigger == "start"
            and new_status == "review"
            and should_skip_review(_row_to_dict(row))
        ):
            new_status = "done"

        now = _now()
        agent_id = get_agent_id()  # Get current agent_id for updated_by
        status_label = "cancelled" if trigger == "cancel" else None
        conn.execute(
            "UPDATE work_items SET status=?, status_label=?, role_changed_at=?, updated_at=?, updated_by=? WHERE id=?",
            (new_status, status_label, now, now, agent_id, item_id),
        )
        conn.commit()

        # Scheduled item requeue: if completing and item has a schedule, requeue it
        if new_status == "done" and row["schedule"]:
            new_next_run = (
                croniter(row["schedule"], datetime.now(UTC))
                .get_next(datetime)
                .isoformat()
            )
            conn.execute(
                "UPDATE work_items SET status='queue', previous_status=NULL, next_run_at=?, updated_at=?, updated_by=? WHERE id=?",
                (new_next_run, now, agent_id, item_id),
            )
            conn.commit()

        result = _row_to_dict(
            conn.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
        )

        # Find items unblocked by this transition
        unblocked = []
        if new_status in TERMINAL:
            unblocked = _find_newly_unblocked(conn, item_id)

        # Reopen cascade: if reopening, cascade parent from terminal to work
        if trigger == "reopen" and row["parent_id"]:
            parent = conn.execute(
                "SELECT * FROM work_items WHERE id=?", (row["parent_id"],)
            ).fetchone()
            if parent and parent["status"] in TERMINAL:
                conn.execute(
                    "UPDATE work_items SET status='work', status_label=NULL, role_changed_at=?, updated_at=?, updated_by=? WHERE id=?",
                    (now, now, agent_id, parent["id"]),
                )
                conn.commit()
                result["parent_reopened"] = True

        result["unblocked_items"] = unblocked
        return result
    finally:
        conn.close()


def advance_items_batch(transitions: list[dict]) -> dict:
    """Batch advance multiple items. Each entry: {item_id, trigger}."""
    results = []
    all_unblocked = []
    succeeded = 0
    failed = 0
    for t in transitions:
        try:
            result = advance_item(t["item_id"], t["trigger"])
            results.append(
                {
                    "item_id": t["item_id"],
                    "trigger": t["trigger"],
                    "applied": True,
                    "new_status": result["status"],
                }
            )
            all_unblocked.extend(result.get("unblocked_items", []))
            succeeded += 1
        except (ValueError, ToolError) as e:
            results.append(
                {
                    "item_id": t["item_id"],
                    "trigger": t["trigger"],
                    "applied": False,
                    "error": str(e),
                }
            )
            failed += 1
    return {
        "results": results,
        "summary": {
            "total": len(transitions),
            "succeeded": succeeded,
            "failed": failed,
        },
        "all_unblocked_items": all_unblocked,
    }


def get_next_status(item_id: str, trigger: str) -> dict:
    """Read-only preview of what would happen with a given trigger."""
    if trigger not in TRANSITIONS and trigger != "resume":
        return {"error": f"Invalid trigger: {trigger}"}
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return {"error": f"Item {item_id} not found"}
        current = row["status"]
        if trigger == "resume":
            if current != "blocked":
                return {
                    "can_advance": False,
                    "reason": f"Can only resume blocked items, current: {current}",
                }
            return {
                "can_advance": True,
                "current": current,
                "next": row["previous_status"] or "work",
                "trigger": trigger,
            }
        if current not in TRANSITIONS.get(trigger, {}):
            return {"can_advance": False, "reason": f"Cannot {trigger} from {current}"}
        # Check deps
        blockers = []
        if trigger in ("start", "complete") and current == "queue":
            blockers = _get_unsatisfied_blockers(conn, item_id)
        if blockers:
            return {
                "can_advance": False,
                "reason": "Blocked by dependencies",
                "blockers": [{"id": b["id"], "title": b["title"]} for b in blockers],
            }
        # Check gates
        if trigger in ("start", "complete"):
            item_dict = _row_to_dict(row)
            notes = [
                _row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM notes WHERE item_id=?", (item_id,)
                ).fetchall()
            ]
            gate = check_gate(item_dict, notes, TRANSITIONS[trigger][current])
            if not gate["can_advance"]:
                return {
                    "can_advance": False,
                    "reason": "Missing required notes",
                    "missing": gate["missing"],
                    "guidance": gate["guidance"],
                }
        if trigger == "cancel" and not can_cancel(_row_to_dict(row)):
            return {"can_advance": False, "reason": "Item has permanent lifecycle"}
        return {
            "can_advance": True,
            "current": current,
            "next": TRANSITIONS[trigger][current],
            "trigger": trigger,
        }
    finally:
        conn.close()


def _unsatisfied_blockers_for(conn, item_ids: list[str]) -> dict[str, list[dict]]:
    """Unsatisfied blockers de N itens numa consulta (mata o N+1).

    Mesma regra de `_get_unsatisfied_blockers`, só batch: o consumidor que
    avalia a fila inteira fazia uma consulta por item — 115 queries num board de
    64 itens, medido no G5 da FEAT-1.
    """
    if not item_ids:
        return {}
    status_rank = {
        "queue": 0,
        "work": 1,
        "review": 2,
        "done": 3,
        "cancelled": 3,
        "archived": 3,
        "blocked": 0,
    }
    placeholders = ",".join("?" * len(item_ids))
    rows = conn.execute(
        f"""
        SELECT wi.*, d.unblock_at, d.dep_type, d.to_id AS blocked_item
        FROM dependencies d
        JOIN work_items wi ON wi.id = d.from_id
        WHERE d.to_id IN ({placeholders})
    """,
        list(item_ids),
    ).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        dep_type = r["dep_type"] if "dep_type" in r.keys() else "blocks"
        if dep_type == "relates_to":
            continue
        unblock_at = r["unblock_at"] if "unblock_at" in r.keys() else "done"
        if status_rank.get(r["status"], 0) < status_rank.get(unblock_at, 3):
            # G5: o objeto aninhado em `blocked_by` segue a mesma regra de
            # null-strip da raiz (R-D1a/b/c) — é "todo item" do payload de
            # get_blocked_items, não só a raiz.
            entry = _row_to_dict(r, drop_nulls=True)
            # O alias existe só para agrupar; não faz parte do payload histórico.
            blocked_item = entry.pop("blocked_item")
            out.setdefault(blocked_item, []).append(entry)
    return out


def _get_unsatisfied_blockers(conn, item_id: str) -> list[dict]:
    """Check blockers respecting unblock_at threshold. Ignores relates_to deps.
    Status order: queue(0) < work(1) < review(2) < done(3). cancelled counts as done."""
    return _unsatisfied_blockers_for(conn, [item_id]).get(item_id, [])


def _find_newly_unblocked(conn, completed_id: str) -> list[dict]:
    dependents = conn.execute(
        "SELECT to_id FROM dependencies WHERE from_id=?", (completed_id,)
    ).fetchall()
    unblocked = []
    for dep in dependents:
        blockers = _get_unsatisfied_blockers(conn, dep["to_id"])
        if not blockers:
            row = conn.execute(
                "SELECT * FROM work_items WHERE id=?", (dep["to_id"],)
            ).fetchone()
            if row and row["status"] not in TERMINAL:
                unblocked.append(_row_to_dict(row))
    return unblocked
