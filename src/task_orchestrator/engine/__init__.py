"""Workflow engine — status transitions, dependency checks, queries.

Status flow: queue → work → review → done
Any non-terminal status can go to: blocked (via block trigger) → resume → previous status
Terminal statuses: done, cancelled
"""

import sqlite3
import uuid
from datetime import datetime, timezone, timedelta

from ..db import get_connection
from ..schemas import (
    check_gate,
    should_skip_review,
    can_cancel,
    get_schema_for_item,
    should_auto_reopen,
)

from croniter import croniter, CroniterBadCronError

from ..workspace import get_workspace_config

# Import from base module
from .base import (
    ToolError,
    VALID_STATUSES,
    TERMINAL,
    PRIORITIES,
    PRIORITY_ORDER,
    TRANSITIONS,
    resolve_short_id,
    _parse_dt,
    _now,
    _uid,
    _row_to_dict,
    _validate_priority,
    _validate_due_at,
    _workspace_tag_filter,
)

# Import from archive module
from .archive import archive_items, archive_stats, archive_list

# Import from portability module
from .portability import export_graph, import_graph, _get_table_columns, _insert_rows, _sort_items_by_depth

# Import from dependencies module
from .dependencies import add_dependency, add_dependency_pattern, remove_dependency, get_dependencies, query_dependencies_bfs, _would_create_cycle

# Import from notes module
from .notes import upsert_note, delete_note, get_notes

# Import from items module
from .items import (
    create_item, create_items_batch, update_item, delete_item, delete_items_batch,
    _delete_descendants, get_item, query_items, _fts_search, get_children,
    get_ancestors, _get_depth
)

# Import from transitions module
from .transitions import advance_item, advance_items_batch, get_next_status, _get_unsatisfied_blockers, _find_newly_unblocked

# Import from queries module
from .queries import _get_items_by_due_date, _get_scheduled_upcoming, get_next_item, get_blocked_items, get_context

# Import from metrics module
from .metrics import get_metrics, get_project_graph_metrics

# Import from workspace_view module
from .workspace_view import get_workspace_context, get_execution_stack


# --- Bulk ---


def create_work_tree(
    root: dict,
    children: list[dict] | None = None,
    deps: list[dict] | None = None,
    create_notes: bool = False,
) -> dict:
    root_item = create_item(**root)
    ref_map = {"root": root_item["id"]}
    created = [root_item]
    for child in children or []:
        ref = child.pop("ref", None)
        child["parent_id"] = root_item["id"]
        item = create_item(**child)
        if ref:
            ref_map[ref] = item["id"]
        created.append(item)
    dep_results = []
    for dep in deps or []:
        fid = ref_map.get(dep["from"], dep["from"])
        tid = ref_map.get(dep["to"], dep["to"])
        dep_results.append(
            add_dependency(
                fid,
                tid,
                dep_type=dep.get("type", "blocks"),
                unblock_at=dep.get("unblock_at", "done"),
            )
        )
    # Auto-create blank notes from schemas
    notes_created = []
    if create_notes:
        for item in created:
            schema = get_schema_for_item(
                item.get("item_type", ""), item.get("tags", "")
            )
            if schema:
                for note_def in schema["notes"]:
                    note = upsert_note(
                        item["id"], note_def["key"], "", note_def["role"]
                    )
                    notes_created.append(
                        {
                            "item_id": item["id"],
                            "key": note_def["key"],
                            "role": note_def["role"],
                            "id": note["id"],
                        }
                    )
    return {
        "root": root_item,
        "children": created[1:],
        "dependencies": dep_results,
        "ref_map": ref_map,
        "notes": notes_created,
    }


def complete_tree(parent_id: str) -> dict:
    """Batch-complete all non-terminal descendants in topological order."""
    conn = get_connection()
    try:
        # Get all descendants
        def _get_all_descendants(pid):
            items = []
            rows = conn.execute(
                "SELECT * FROM work_items WHERE parent_id=?", (pid,)
            ).fetchall()
            for r in rows:
                items.append(_row_to_dict(r))
                items.extend(_get_all_descendants(r["id"]))
            return items

        descendants = _get_all_descendants(parent_id)
        completed = []
        skipped = []
        for item in descendants:
            if item["status"] in TERMINAL:
                skipped.append(
                    {"id": item["id"], "title": item["title"], "status": item["status"]}
                )
                continue
            try:
                result = advance_item(item["id"], "complete")
                completed.append(
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "new_status": result["status"],
                    }
                )
            except ValueError as e:
                skipped.append(
                    {"id": item["id"], "title": item["title"], "reason": str(e)}
                )
        return {"completed": completed, "skipped": skipped}
    finally:
        conn.close()


def get_project_graph_metrics(workspace: str | None = None, root_id: str | None = None) -> dict:
    """Compute project graph metrics: critical path, impact scores, position."""
    conn = get_connection()
    try:
        ws_clause, ws_params = _workspace_tag_filter(workspace)
        ws_where = f"WHERE {ws_clause}" if ws_clause else ""

        rows = conn.execute(
            f"SELECT * FROM work_items {ws_where}", ws_params
        ).fetchall()
        items = [_row_to_dict(r) for r in rows]

        if not items:
            return {
                "critical_path": [],
                "critical_path_length": 0,
                "next_on_critical_path": None,
                "impact_scores": [],
                "current_position": {
                    "active_item": None,
                    "on_critical_path": False,
                    "distance_to_end": 0,
                },
                "project_health": {
                    "total": 0,
                    "done": 0,
                    "remaining": 0,
                    "parallelizable_now": 0,
                    "bottlenecks": [],
                },
            }

        item_ids = {i["id"] for i in items}
        item_map = {i["id"]: i for i in items}

        # Load deps scoped to these items
        all_deps = conn.execute("SELECT * FROM dependencies").fetchall()
        deps = [d for d in all_deps if d["from_id"] in item_ids and d["to_id"] in item_ids and d["dep_type"] != "relates_to"]

        # Build adjacency (from_id blocks to_id, edge: from -> to)
        adj: dict[str, list[str]] = {i: [] for i in item_ids}
        in_adj: dict[str, list[str]] = {i: [] for i in item_ids}
        for d in deps:
            adj[d["from_id"]].append(d["to_id"])
            in_adj[d["to_id"]].append(d["from_id"])

        # Filter to undone items for critical path
        undone_ids = {i["id"] for i in items if i["status"] not in TERMINAL}

        # Longest path in DAG of undone items (weight=1 per node)
        # Use dynamic programming on topological order
        # Topo sort on undone subgraph
        undone_adj: dict[str, list[str]] = {i: [] for i in undone_ids}
        undone_in_degree: dict[str, int] = {i: 0 for i in undone_ids}
        for d in deps:
            if d["from_id"] in undone_ids and d["to_id"] in undone_ids:
                undone_adj[d["from_id"]].append(d["to_id"])
                undone_in_degree[d["to_id"]] += 1

        # Kahn's algorithm for topo sort
        queue_nodes = [n for n in undone_ids if undone_in_degree[n] == 0]
        topo_order = []
        while queue_nodes:
            queue_nodes.sort()  # deterministic
            node = queue_nodes.pop(0)
            topo_order.append(node)
            for nb in undone_adj[node]:
                undone_in_degree[nb] -= 1
                if undone_in_degree[nb] == 0:
                    queue_nodes.append(nb)

        # Longest path DP
        dist: dict[str, int] = {n: 1 for n in topo_order}
        pred: dict[str, str | None] = {n: None for n in topo_order}
        for node in topo_order:
            for nb in undone_adj[node]:
                if dist[node] + 1 > dist[nb]:
                    dist[nb] = dist[node] + 1
                    pred[nb] = node

        # Find the end of the longest path
        critical_path: list[str] = []
        if dist:
            end_node = max(dist, key=lambda n: dist[n])
            # Reconstruct path
            path = []
            cur = end_node
            while cur is not None:
                path.append(cur)
                cur = pred[cur]
            critical_path = list(reversed(path))

        critical_path_set = set(critical_path)

        # Impact scores: BFS outbound from each undone item counting transitive downstream
        impact_scores = []
        for item_id in undone_ids:
            visited = set()
            bfs_queue = list(adj.get(item_id, []))
            while bfs_queue:
                current = bfs_queue.pop(0)
                if current in visited or current == item_id:
                    continue
                if current not in undone_ids:
                    continue
                visited.add(current)
                bfs_queue.extend(adj.get(current, []))
            impact_scores.append({
                "item_id": item_id,
                "title": item_map[item_id]["title"],
                "unblocks_count": len(visited),
            })
        impact_scores.sort(key=lambda x: -x["unblocks_count"])

        # Current position: find active item (status=work)
        active_items = [i for i in items if i["status"] == "work"]
        active_item = active_items[0] if active_items else None
        active_id = active_item["id"] if active_item else None
        on_critical_path = active_id in critical_path_set if active_id else False
        distance_to_end = 0
        if active_id and active_id in critical_path_set:
            idx = critical_path.index(active_id)
            distance_to_end = len(critical_path) - idx

        # Next on critical path: first item on critical path that is actionable (queue/work with no unsatisfied deps)
        next_on_cp = None
        for cp_id in critical_path:
            item = item_map[cp_id]
            if item["status"] in ("work",):
                next_on_cp = cp_id
                break
            if item["status"] == "queue":
                blockers = _get_unsatisfied_blockers(conn, cp_id)
                if not blockers:
                    next_on_cp = cp_id
                    break

        # Project health
        total = len(items)
        done_count = sum(1 for i in items if i["status"] in TERMINAL)
        remaining = total - done_count

        # Parallelizable: queue items with no pending deps
        parallelizable = 0
        for i in items:
            if i["status"] == "queue":
                blockers = _get_unsatisfied_blockers(conn, i["id"])
                if not blockers:
                    parallelizable += 1

        # Bottlenecks: items with highest fan-out (outbound degree in undone graph)
        fanout = {}
        for d in deps:
            if d["from_id"] in undone_ids and d["to_id"] in undone_ids:
                fanout[d["from_id"]] = fanout.get(d["from_id"], 0) + 1
        # Top bottlenecks (fan-out >= 3 or top 3)
        sorted_fanout = sorted(fanout.items(), key=lambda x: -x[1])
        bottlenecks = [item_id for item_id, count in sorted_fanout if count >= 3]
        if not bottlenecks and sorted_fanout:
            bottlenecks = [sorted_fanout[0][0]] if sorted_fanout[0][1] > 1 else []

        return {
            "critical_path": critical_path,
            "critical_path_length": len(critical_path),
            "next_on_critical_path": next_on_cp,
            "impact_scores": impact_scores,
            "current_position": {
                "active_item": active_id,
                "on_critical_path": on_critical_path,
                "distance_to_end": distance_to_end,
            },
            "project_health": {
                "total": total,
                "done": done_count,
                "remaining": remaining,
                "parallelizable_now": parallelizable,
                "bottlenecks": bottlenecks,
            },
        }
    finally:
        conn.close()
