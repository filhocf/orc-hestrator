from datetime import datetime, timezone, timedelta

from ..db import get_connection
from .base import _now, _row_to_dict, _workspace_tag_filter


def archive_items(workspace: str | None = None, days: int = 30) -> dict:
    """Move items in 'done' status older than `days` to 'archived'."""
    conn = get_connection()
    try:
        now_dt = datetime.now(timezone.utc)
        cutoff = (now_dt - timedelta(days=days)).isoformat()
        ws_clause, ws_params = _workspace_tag_filter(workspace)
        ws_and = f" AND {ws_clause}" if ws_clause else ""

        rows = conn.execute(
            f"SELECT id FROM work_items WHERE status='done' AND updated_at < ? {ws_and}",
            [cutoff] + ws_params,
        ).fetchall()

        now = _now()
        ids = [r["id"] for r in rows]
        if ids:
            conn.execute(
                f"UPDATE work_items SET status='archived', role_changed_at=?, updated_at=? WHERE status='done' AND updated_at < ? {ws_and}",
                [now, now, cutoff] + ws_params,
            )
        conn.commit()
        return {"archived_count": len(ids), "archived_ids": ids}
    finally:
        conn.close()


def archive_stats(workspace: str | None = None, days: int = 30) -> dict:
    """Return count of archived items and items eligible for archiving."""
    conn = get_connection()
    try:
        ws_clause, ws_params = _workspace_tag_filter(workspace)
        ws_and = f" AND {ws_clause}" if ws_clause else ""

        archived_count = conn.execute(
            f"SELECT COUNT(*) as cnt FROM work_items WHERE status='archived' {ws_and}",
            ws_params,
        ).fetchone()["cnt"]

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        eligible_count = conn.execute(
            f"SELECT COUNT(*) as cnt FROM work_items WHERE status='done' AND updated_at < ? {ws_and}",
            [cutoff] + ws_params,
        ).fetchone()["cnt"]

        return {
            "archived_count": archived_count,
            "eligible_count": eligible_count,
            "archive_after_days": days,
        }
    finally:
        conn.close()


def archive_list(workspace: str | None = None) -> list[dict]:
    """Return all archived items, optionally filtered by workspace."""
    conn = get_connection()
    try:
        ws_clause, ws_params = _workspace_tag_filter(workspace)
        ws_and = f" AND {ws_clause}" if ws_clause else ""

        rows = conn.execute(
            f"SELECT * FROM work_items WHERE status='archived' {ws_and} ORDER BY updated_at DESC",
            ws_params,
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()