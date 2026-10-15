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


def _sort_items_topologically(conn, items: list[dict], mode: str) -> list[dict]:
    """Sort items in topological order: every parent comes before its children.
    
    Handles hierarchies of any depth. For orphan parents (parent_id not in batch 
    and not in database), treats them as roots (parent_id=None) to avoid FK errors.
    
    Args:
        conn: Database connection to check existing items
        items: List of item dicts to sort
        mode: 'merge' or 'replace' - affects orphan parent handling
    """
    if not items:
        return items
    
    # Create a mapping of id -> item for quick lookup
    item_map = {item["id"]: item for item in items}
    batch_ids = set(item_map.keys())
    
    # For merge mode, check which parent_ids already exist in database
    existing_ids = set()
    if mode == "merge":
        # Get all referenced parent_ids that are not in the current batch
        referenced_parents = {item.get("parent_id") for item in items 
                            if item.get("parent_id") and item.get("parent_id") not in batch_ids}
        referenced_parents.discard(None)
        
        if referenced_parents:
            placeholders = ",".join("?" for _ in referenced_parents)
            existing_rows = conn.execute(
                f"SELECT id FROM work_items WHERE id IN ({placeholders})", 
                list(referenced_parents)
            ).fetchall()
            existing_ids = {row["id"] for row in existing_rows}
    
    # Normalize orphan parents: if parent_id points to non-existent parent, make it a root
    normalized_items = []
    for item in items:
        parent_id = item.get("parent_id")
        if parent_id and parent_id not in batch_ids and parent_id not in existing_ids:
            # Orphan parent: not in batch and not in database -> make it a root
            item_copy = item.copy()
            item_copy["parent_id"] = None
            normalized_items.append(item_copy)
        else:
            normalized_items.append(item)
    
    # Topological sort using Kahn's algorithm (wave-based emission)
    result = []
    remaining = normalized_items.copy()
    emitted_ids = existing_ids.copy()  # Start with existing DB items as "already emitted"
    
    while remaining:
        # Find items ready to emit: parent_id is None or parent already emitted
        ready = []
        still_waiting = []
        
        for item in remaining:
            parent_id = item.get("parent_id")
            if parent_id is None or parent_id in emitted_ids:
                ready.append(item)
            else:
                still_waiting.append(item)
        
        if not ready:
            # No progress possible - should not happen in a valid tree, but handle defensively
            # Emit remaining items as roots (this preserves data, though structure may be wrong)
            for item in still_waiting:
                item_copy = item.copy()
                item_copy["parent_id"] = None
                ready.append(item_copy)
            still_waiting = []
        
        # Emit ready items in deterministic order (by id for stability)
        ready.sort(key=lambda x: x["id"])
        result.extend(ready)
        
        # Mark emitted items
        for item in ready:
            emitted_ids.add(item["id"])
        
        remaining = still_waiting
    
    return result


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
        sorted_items = _sort_items_topologically(conn, data.get("items", []), mode)
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