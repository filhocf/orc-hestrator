from ..db import get_connection
from ..workspace import get_workspace_config
from .base import ToolError, _row_to_dict, _workspace_tag_filter
from .queries import get_next_item, get_blocked_items
from .items import _get_depth


def get_workspace_context(workspace_name: str, verbosity: str = "standard") -> dict:
    """Get workspace context at varying verbosity levels: minimal, standard, full."""
    if verbosity not in ("minimal", "standard", "full"):
        raise ToolError(
            "VALIDATION",
            f"Invalid verbosity: {verbosity}. Valid: minimal, standard, full",
            "verbosity",
        )
    config = get_workspace_config(workspace_name)
    if config is None:
        raise ToolError(
            "NOT_FOUND", f"Workspace '{workspace_name}' not found", "workspace_name"
        )

    conn = get_connection()
    try:
        ws_clause, ws_params = _workspace_tag_filter(workspace_name)
        ws_and = f" AND {ws_clause}" if ws_clause else ""

        # Status counts
        rows = conn.execute(
            f"SELECT status, COUNT(*) as c FROM work_items WHERE 1=1{ws_and} GROUP BY status",
            ws_params,
        ).fetchall()
        status_counts = {r["status"]: r["c"] for r in rows}

        result = {
            "workspace": workspace_name,
            "brief": config.get("description", ""),
            "status_counts": status_counts,
            "memory_tags": config.get("memory_tags", []),
            "next_item": get_next_item(workspace=workspace_name),
        }

        if verbosity in ("standard", "full"):
            active_rows = conn.execute(
                f"SELECT * FROM work_items WHERE status='work'{ws_and}",
                ws_params,
            ).fetchall()
            result["active_items"] = [_row_to_dict(r) for r in active_rows]
            result["blocked_items"] = get_blocked_items(workspace=workspace_name)

        if verbosity == "full":
            # Get all item IDs in this workspace
            item_rows = conn.execute(
                f"SELECT id FROM work_items WHERE 1=1{ws_and}", ws_params
            ).fetchall()
            item_ids = [r["id"] for r in item_rows]
            decisions = []
            if item_ids:
                placeholders = ",".join("?" * len(item_ids))
                note_rows = conn.execute(
                    f"SELECT * FROM notes WHERE item_id IN ({placeholders}) AND key LIKE '%decision%' ORDER BY updated_at DESC LIMIT 20",
                    item_ids,
                ).fetchall()
                decisions = [_row_to_dict(r) for r in note_rows]
            result["recent_decisions"] = decisions

        return result
    finally:
        conn.close()


def get_execution_stack(workspace: str | None = None) -> list[dict]:
    """Return current execution stack — items in work/blocked ordered by depth.

    Each frame: {depth, item_id, title, status, active, held_at, execution_state}
    """
    conn = get_connection()
    try:
        ws_clause, ws_params = _workspace_tag_filter(workspace)
        ws_and = f" AND {ws_clause}" if ws_clause else ""

        rows = conn.execute(
            f"SELECT * FROM work_items WHERE status IN ('work', 'blocked') {ws_and}",
            ws_params,
        ).fetchall()

        if not rows:
            return []

        items = [_row_to_dict(r) for r in rows]

        # Compute depth for each item
        for item in items:
            item["_depth"] = _get_depth(conn, item["id"])

        # Fetch execution-state notes
        item_ids = [item["id"] for item in items]
        placeholders = ",".join("?" for _ in item_ids)
        note_rows = conn.execute(
            f"SELECT item_id, body FROM notes WHERE item_id IN ({placeholders}) AND key='execution-state'",
            item_ids,
        ).fetchall()
        note_map = {r["item_id"]: r["body"] for r in note_rows}

        # Build frames: blocked (suspended) first by depth, then work (active) by depth
        items.sort(key=lambda x: (0 if x["status"] == "blocked" else 1, x["_depth"]))

        return [
            {
                "depth": item["_depth"],
                "item_id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "active": item["status"] == "work",
                "held_at": item["role_changed_at"] if item["status"] == "blocked" else None,
                "execution_state": note_map.get(item["id"]),
            }
            for item in items
        ]
    finally:
        conn.close()