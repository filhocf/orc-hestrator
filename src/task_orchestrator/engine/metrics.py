from datetime import UTC, datetime, timedelta

from ..db import get_connection
from .base import TERMINAL, _parse_dt, _row_to_dict, _workspace_tag_filter
from .transitions import _get_unsatisfied_blockers


def get_metrics(days: int = 30, workspace: str | None = None) -> dict:
    """Work metrics: throughput, lead time, WIP, stale ratio, breakdowns."""
    conn = get_connection()
    try:
        ws_clause, ws_params = _workspace_tag_filter(workspace)
        ws_and = f"AND {ws_clause}" if ws_clause else ""

        now_dt = datetime.now(UTC)
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


def get_project_graph_metrics(
    workspace: str | None = None, root_id: str | None = None
) -> dict:
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
        deps = [
            d
            for d in all_deps
            if d["from_id"] in item_ids
            and d["to_id"] in item_ids
            and d["dep_type"] != "relates_to"
        ]

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
            impact_scores.append(
                {
                    "item_id": item_id,
                    "title": item_map[item_id]["title"],
                    "unblocks_count": len(visited),
                }
            )
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
