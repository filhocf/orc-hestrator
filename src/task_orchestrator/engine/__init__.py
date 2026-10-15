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


# --- Metrics ---


def get_metrics(days: int = 30, workspace: str | None = None) -> dict:
    """Work metrics: throughput, lead time, WIP, stale ratio, breakdowns."""
    conn = get_connection()
    try:
        ws_clause, ws_params = _workspace_tag_filter(workspace)
        ws_and = f"AND {ws_clause}" if ws_clause else ""

        now_dt = datetime.now(timezone.utc)
        cutoff = (now_dt - timedelta(days=days)).isoformat()
        stale_cutoff = (now_dt - timedelta(days=7)).isoformat()

        # Throughput per week (done+archived items in period, grouped by ISO week)
        rows = conn.execute(
            f"SELECT updated_at FROM work_items WHERE status IN ('done','archived') AND updated_at >= ? {ws_and}",
            [cutoff] + ws_params,
        ).fetchall()
        week_counts: dict[str, int] = {}
        for r in rows:
            dt = _parse_dt(r["updated_at"])
            iso = dt.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
            week_counts[key] = week_counts.get(key, 0) + 1
        throughput = [{"week": w, "count": c} for w, c in sorted(week_counts.items())]

        # Lead time avg (done+archived items in period)
        lt_rows = conn.execute(
            f"SELECT created_at, updated_at FROM work_items WHERE status IN ('done','archived') AND updated_at >= ? {ws_and}",
            [cutoff] + ws_params,
        ).fetchall()
        if lt_rows:
            total_secs = sum(
                (
                    _parse_dt(r["updated_at"]) - _parse_dt(r["created_at"])
                ).total_seconds()
                for r in lt_rows
            )
            lead_time_avg = total_secs / len(lt_rows)
        else:
            lead_time_avg = 0.0

        # WIP
        wip = conn.execute(
            f"SELECT COUNT(*) as cnt FROM work_items WHERE status='work' {ws_and}",
            ws_params,
        ).fetchone()["cnt"]

        # Stale ratio
        non_terminal = conn.execute(
            f"SELECT COUNT(*) as cnt FROM work_items WHERE status NOT IN ('done','cancelled','archived') {ws_and}",
            ws_params,
        ).fetchone()["cnt"]
        stale = conn.execute(
            f"SELECT COUNT(*) as cnt FROM work_items WHERE status NOT IN ('done','cancelled','archived') AND updated_at < ? {ws_and}",
            [stale_cutoff] + ws_params,
        ).fetchone()["cnt"]
        stale_ratio = (stale / non_terminal * 100) if non_terminal else 0.0

        # By priority (done in period)
        by_priority = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in conn.execute(
            f"SELECT priority, COUNT(*) as cnt FROM work_items WHERE status IN ('done','archived') AND updated_at >= ? {ws_and} GROUP BY priority",
            [cutoff] + ws_params,
        ).fetchall():
            if r["priority"] in by_priority:
                by_priority[r["priority"]] = r["cnt"]

        # By tag (top 10 tags across non-terminal items)
        tag_counts: dict[str, int] = {}
        for r in conn.execute(
            f"SELECT tags FROM work_items WHERE status NOT IN ('done','cancelled','archived') AND tags != '' {ws_and}",
            ws_params,
        ).fetchall():
            for tag in r["tags"].split(","):
                tag = tag.strip()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        by_tag = dict(sorted(tag_counts.items(), key=lambda x: -x[1])[:10])

        # Total items
        ws_where = f"WHERE {ws_clause}" if ws_clause else ""
        total = conn.execute(
            f"SELECT COUNT(*) as cnt FROM work_items {ws_where}", ws_params
        ).fetchone()["cnt"]

        return {
            "throughput_per_week": throughput,
            "lead_time_avg_seconds": lead_time_avg,
            "wip": wip,
            "stale_ratio": stale_ratio,
            "by_priority": by_priority,
            "by_tag": by_tag,
            "total_items": total,
            "period_days": days,
        }
    finally:
        conn.close()





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
