import sqlite3

from ..db import get_connection
from .base import ToolError, _now, _row_to_dict, _uid


def add_dependency(
    from_id: str, to_id: str, dep_type: str = "blocks", unblock_at: str = "done"
) -> dict:
    """Add dependency. dep_type: blocks, is_blocked_by, relates_to.
    unblock_at: status at which the blocker unblocks (default: done).
    Valid: done, review, work. RELATES_TO deps cannot have unblock_at."""
    if from_id == to_id:
        raise ToolError("VALIDATION", "Cannot depend on self", "from_id")
    valid_types = {"blocks", "is_blocked_by", "relates_to"}
    dep_type = dep_type.lower().replace("-", "_")
    if dep_type not in valid_types:
        raise ToolError(
            "VALIDATION",
            f"Invalid dep_type: {dep_type}. Valid: {sorted(valid_types)}",
            "dep_type",
        )
    if dep_type == "relates_to" and unblock_at != "done":
        raise ToolError(
            "VALIDATION",
            "RELATES_TO dependencies cannot have unblock_at threshold",
            "unblock_at",
        )
    valid_unblock = {"done", "review", "work"}
    if unblock_at not in valid_unblock:
        raise ToolError(
            "VALIDATION",
            f"Invalid unblock_at: {unblock_at}. Valid: {sorted(valid_unblock)}",
            "unblock_at",
        )
    # IS_BLOCKED_BY is stored as BLOCKS with swapped direction
    if dep_type == "is_blocked_by":
        from_id, to_id = to_id, from_id
        dep_type = "blocks"
    conn = get_connection()
    try:
        for fid in (from_id, to_id):
            if not conn.execute(
                "SELECT id FROM work_items WHERE id=?", (fid,)
            ).fetchone():
                raise ToolError("NOT_FOUND", f"Item {fid} not found", "from_id")
        if dep_type != "relates_to" and _would_create_cycle(conn, from_id, to_id):
            raise ToolError("CONFLICT", "Dependency would create a cycle", "from_id")
        dep_id = _uid()
        now = _now()
        try:
            conn.execute(
                "INSERT INTO dependencies (id,from_id,to_id,dep_type,unblock_at,created_at) VALUES (?,?,?,?,?,?)",
                (dep_id, from_id, to_id, dep_type, unblock_at, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ToolError(
                "CONFLICT", f"Dependency {from_id} → {to_id} already exists", "from_id"
            )
        return _row_to_dict(
            conn.execute("SELECT * FROM dependencies WHERE id=?", (dep_id,)).fetchone()
        )
    finally:
        conn.close()


def add_dependency_pattern(item_ids: list[str], pattern: str = "linear") -> list[dict]:
    """Create dependencies using pattern shortcuts: linear, fan-out, fan-in."""
    if len(item_ids) < 2:
        raise ToolError(
            "VALIDATION", "Need at least 2 items for a dependency pattern", "item_ids"
        )
    results = []
    if pattern == "linear":
        for i in range(len(item_ids) - 1):
            results.append(add_dependency(item_ids[i], item_ids[i + 1]))
    elif pattern == "fan-out":
        source = item_ids[0]
        for target in item_ids[1:]:
            results.append(add_dependency(source, target))
    elif pattern == "fan-in":
        target = item_ids[-1]
        for source in item_ids[:-1]:
            results.append(add_dependency(source, target))
    else:
        raise ToolError(
            "VALIDATION",
            f"Invalid pattern: {pattern}. Valid: linear, fan-out, fan-in",
            "pattern",
        )
    return results


def remove_dependency(from_id: str, to_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM dependencies WHERE from_id=? AND to_id=?", (from_id, to_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_dependencies(item_id: str, direction: str = "both") -> dict:
    conn = get_connection()
    try:
        blocks = []
        blocked_by = []
        if direction in ("outbound", "both"):
            rows = conn.execute(
                """
                SELECT d.*, wi.title as to_title, wi.status as to_status
                FROM dependencies d JOIN work_items wi ON wi.id=d.to_id WHERE d.from_id=?
            """,
                (item_id,),
            ).fetchall()
            blocks = [_row_to_dict(r) for r in rows]
        if direction in ("inbound", "both"):
            rows = conn.execute(
                """
                SELECT d.*, wi.title as from_title, wi.status as from_status
                FROM dependencies d JOIN work_items wi ON wi.id=d.from_id WHERE d.to_id=?
            """,
                (item_id,),
            ).fetchall()
            blocked_by = [_row_to_dict(r) for r in rows]
        return {"blocks": blocks, "blocked_by": blocked_by}
    finally:
        conn.close()


def query_dependencies_bfs(
    item_id: str, direction: str = "outbound", max_depth: int = 10
) -> list[dict]:
    """BFS traversal of dependency graph."""
    conn = get_connection()
    try:
        visited = set()
        result = []
        queue = [(item_id, 0)]
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            if direction == "outbound":
                rows = conn.execute(
                    """
                    SELECT d.*, wi.title, wi.status, wi.priority
                    FROM dependencies d JOIN work_items wi ON wi.id=d.to_id WHERE d.from_id=?
                """,
                    (current,),
                ).fetchall()
                for r in rows:
                    item = _row_to_dict(r)
                    item["depth"] = depth + 1
                    result.append(item)
                    queue.append((r["to_id"], depth + 1))
            else:
                rows = conn.execute(
                    """
                    SELECT d.*, wi.title, wi.status, wi.priority
                    FROM dependencies d JOIN work_items wi ON wi.id=d.from_id WHERE d.to_id=?
                """,
                    (current,),
                ).fetchall()
                for r in rows:
                    item = _row_to_dict(r)
                    item["depth"] = depth + 1
                    result.append(item)
                    queue.append((r["from_id"], depth + 1))
        return result
    finally:
        conn.close()


def _would_create_cycle(conn, from_id: str, to_id: str) -> bool:
    visited = set()
    queue = [to_id]
    while queue:
        current = queue.pop(0)
        if current == from_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        rows = conn.execute(
            "SELECT to_id FROM dependencies WHERE from_id=?", (current,)
        ).fetchall()
        queue.extend(r["to_id"] for r in rows)
    return False
