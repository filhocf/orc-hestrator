from ..db import get_connection
from ..schemas import should_auto_reopen
from .base import TERMINAL, ToolError, _now, _row_to_dict, _uid


def upsert_note(item_id: str, key: str, body: str, role: str = "queue") -> dict:
    conn = get_connection()
    try:
        item = conn.execute(
            "SELECT * FROM work_items WHERE id=?", (item_id,)
        ).fetchone()
        if not item:
            raise ToolError("NOT_FOUND", f"Item {item_id} not found", "item_id")
        now = _now()
        existing = conn.execute(
            "SELECT id FROM notes WHERE item_id=? AND key=?", (item_id, key)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE notes SET body=?, role=?, updated_at=? WHERE id=?",
                (body, role, now, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO notes (id,item_id,key,role,body,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (_uid(), item_id, key, role, body, now, now),
            )
        conn.commit()
        result = _row_to_dict(
            conn.execute(
                "SELECT * FROM notes WHERE item_id=? AND key=?", (item_id, key)
            ).fetchone()
        )
        # Auto-reopen: if item is terminal and schema has auto-reopen lifecycle
        item_dict = _row_to_dict(item)
        if item_dict["status"] in TERMINAL and should_auto_reopen(item_dict):
            conn.execute(
                "UPDATE work_items SET status='queue', updated_at=? WHERE id=?",
                (now, item_id),
            )
            conn.commit()
            result["auto_reopened"] = True
        return result
    finally:
        conn.close()


def delete_note(item_id: str, key: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM notes WHERE item_id=? AND key=?", (item_id, key)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_notes(item_id: str, include_body: bool = True) -> list[dict]:
    conn = get_connection()
    try:
        if include_body:
            rows = conn.execute(
                "SELECT * FROM notes WHERE item_id=? ORDER BY created_at", (item_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, item_id, key, role, created_at, updated_at FROM notes WHERE item_id=? ORDER BY created_at",
                (item_id,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
