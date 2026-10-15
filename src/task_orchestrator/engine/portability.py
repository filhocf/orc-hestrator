from ..db import get_connection
from .base import ToolError, _now, _row_to_dict, _workspace_tag_filter


def export_graph(workspace: str | None = None, tags: list[str] | None = None) -> dict:
    """Export items, notes, and dependencies as a JSON-serializable dict.

    If workspace provided: filter items by workspace tags.
    If tags provided (and no workspace): filter items where any tag matches.
    No params = export all (backward compatible).
    Notes and deps are filtered to only include those related to exported items.
    """
    conn = get_connection()
    try:
        if workspace:
            ws_clause, ws_params = _workspace_tag_filter(workspace)
            items = [
                _row_to_dict(r)
                for r in conn.execute(
                    f"SELECT * FROM work_items WHERE {ws_clause}", ws_params
                ).fetchall()
            ]
        elif tags:
            tag_clauses = " OR ".join("tags LIKE ?" for _ in tags)
            tag_params = [f"%{t}%" for t in tags]
            items = [
                _row_to_dict(r)
                for r in conn.execute(
                    f"SELECT * FROM work_items WHERE {tag_clauses}", tag_params
                ).fetchall()
            ]
        else:
            items = [
                _row_to_dict(r)
                for r in conn.execute("SELECT * FROM work_items").fetchall()
            ]

        item_ids = {i["id"] for i in items}

        if workspace or tags:
            # Filter notes and deps to only exported items
            notes = [
                _row_to_dict(r)
                for r in conn.execute("SELECT * FROM notes").fetchall()
                if r["item_id"] in item_ids
            ]
            deps = [
                _row_to_dict(r)
                for r in conn.execute("SELECT * FROM dependencies").fetchall()
                if r["from_id"] in item_ids and r["to_id"] in item_ids
            ]
        else:
            notes = [
                _row_to_dict(r) for r in conn.execute("SELECT * FROM notes").fetchall()
            ]
            deps = [
                _row_to_dict(r)
                for r in conn.execute("SELECT * FROM dependencies").fetchall()
            ]

        return {
            "items": items,
            "notes": notes,
            "dependencies": deps,
            "exported_at": _now(),
            "version": "0.8.0",
        }
    finally:
        conn.close()


def _get_table_columns(conn, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _insert_rows(conn, table: str, rows: list[dict]):
    if not rows:
        return
    columns = _get_table_columns(conn, table)
    cols = [c for c in columns if c in rows[0]]
    placeholders = ",".join("?" for _ in cols)
    col_names = ",".join(cols)
    values = [tuple(row.get(c) for c in cols) for row in rows]
    conn.executemany(
        f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})", values
    )


def _sort_items_by_depth(items: list[dict]) -> list[dict]:
    """Sort items so parents come before children (parent_id=NULL first)."""
    parents = [i for i in items if not i.get("parent_id")]
    children = [i for i in items if i.get("parent_id")]
    return parents + children


def import_graph(data: dict, mode: str = "merge") -> dict:
    """Import items, notes, and dependencies from an exported dict.

    mode='merge': insert rows that don't exist (skip on conflict).
    mode='replace': delete everything first, then insert all.
    """
    if mode not in ("merge", "replace"):
        raise ToolError(
            "VALIDATION", f"Invalid mode: {mode}. Valid: merge, replace", "mode"
        )
    conn = get_connection()
    try:
        if mode == "replace":
            conn.execute("DELETE FROM dependencies")
            conn.execute("DELETE FROM notes")
            conn.execute("DELETE FROM work_items")
            conn.commit()
        # Sort items: parents first, then children (topological order)
        sorted_items = _sort_items_by_depth(data.get("items", []))
        _insert_rows(conn, "work_items", sorted_items)
        _insert_rows(conn, "notes", data.get("notes", []))
        _insert_rows(conn, "dependencies", data.get("dependencies", []))
        conn.commit()
        counts = {
            "items": conn.execute("SELECT COUNT(*) as c FROM work_items").fetchone()[
                "c"
            ],
            "notes": conn.execute("SELECT COUNT(*) as c FROM notes").fetchone()["c"],
            "dependencies": conn.execute(
                "SELECT COUNT(*) as c FROM dependencies"
            ).fetchone()["c"],
        }
        return {"imported": True, "mode": mode, "counts": counts}
    finally:
        conn.close()