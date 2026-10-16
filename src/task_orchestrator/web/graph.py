"""Pure graph-building helpers shared by the REST API and the legacy Jinja UI.

Extracted from ui/app.py so the REST layer does NOT import the Jinja app (no jinja2 pull,
no coupling to presentation). `build_cytoscape_data` is a pure function: (arc_id, children)
-> {"nodes": [...], "edges": [...]} dict. The legacy UI wraps it with json.dumps.
"""

from ..db import get_connection


def build_cytoscape_data(arc_id: str, children: list[dict]) -> dict:
    """Build Cytoscape.js graph data (waves + deps) for an arc as a plain dict.

    Shows direct children that are waves, have dependencies, or have their own children;
    falls back to all direct children. Root→child edges are added for nodes with no incoming
    dependency edge. Returns {"nodes": [...], "edges": [...]}.
    """
    conn = get_connection()
    try:
        root = conn.execute(
            "SELECT id, title, status FROM work_items WHERE id = ?", (arc_id,)
        ).fetchone()
        if not root:
            return {"nodes": [], "edges": []}

        direct_children = conn.execute(
            "SELECT id, title, status, priority, tags FROM work_items WHERE parent_id = ?",
            (arc_id,),
        ).fetchall()

        all_child_ids = [r["id"] for r in direct_children]
        placeholders = ",".join("?" * len(all_child_ids)) if all_child_ids else "''"

        # Items involved in dependencies
        dep_items = set()
        dep_rows = []
        if all_child_ids:
            dep_rows = conn.execute(
                f"SELECT from_id, to_id FROM dependencies WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders})",
                all_child_ids + all_child_ids,
            ).fetchall()
            for r in dep_rows:
                dep_items.add(r["from_id"])
                dep_items.add(r["to_id"])

        # Filter: show waves + items with deps + items with children
        show_items = []
        for item in direct_children:
            tags = item["tags"] or ""
            has_deps = item["id"] in dep_items
            has_children = (
                conn.execute(
                    "SELECT COUNT(*) FROM work_items WHERE parent_id=?", (item["id"],)
                ).fetchone()[0]
                > 0
            )
            is_wave = "wave" in tags
            if is_wave or has_deps or has_children:
                show_items.append(dict(item))

        if not show_items:
            show_items = [dict(r) for r in direct_children]

        if not show_items:
            return {"nodes": [], "edges": []}

        nodes = [
            {
                "data": {
                    "id": root["id"],
                    "label": root["title"][:40],
                    "status": root["status"] or "queue",
                    "is_root": True,
                }
            }
        ]
        show_ids = set()
        for item in show_items:
            show_ids.add(item["id"])
            nodes.append(
                {
                    "data": {
                        "id": item["id"],
                        "label": item["title"][:35],
                        "status": item.get("status", "queue"),
                        "is_root": False,
                    }
                }
            )

        edges = []
        dep_edges = set()
        if all_child_ids:
            for r in dep_rows:
                if r["from_id"] in show_ids and r["to_id"] in show_ids:
                    edges.append(
                        {"data": {"source": r["from_id"], "target": r["to_id"]}}
                    )
                    dep_edges.add((r["from_id"], r["to_id"]))

        # Root→child edges for items without incoming deps
        items_with_incoming = {to for _, to in dep_edges}
        for item in show_items:
            if item["id"] not in items_with_incoming:
                edges.append({"data": {"source": root["id"], "target": item["id"]}})
    finally:
        conn.close()

    return {"nodes": nodes, "edges": edges}
