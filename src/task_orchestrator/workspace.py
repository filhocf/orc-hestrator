"""Workspace management — persisted in the `workspaces` table (FEAT-6b, RFC-003 R-C1).

Public API kept identical to the previous workspaces.json-backed version:
list_workspaces, create_workspace, update_workspace, delete_workspace,
get_workspace_tags, get_workspace_config. Callers (engine/workspace_view.py,
engine/portability.py) are unaffected.
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from . import db

logger = logging.getLogger(__name__)

_LIST_COLUMNS = ("tags", "memory_tags", "repos", "conventions")


def _now() -> str:
    # Mirrors engine.base._now(). Duplicated (not imported) to avoid a
    # circular import: engine/base.py imports get_workspace_tags from this
    # module, so this module cannot import from engine.base at module level.
    return datetime.now(UTC).isoformat()


def _get_agent_id() -> str | None:
    # Lazy import to avoid the circular import described above.
    from .engine.base import get_agent_id

    return get_agent_id()


def _legacy_json_path() -> str:
    """Path to the legacy workspaces.json, kept for the one-shot import (R-C5).

    Mirrors the pre-FEAT-6b resolution: env override first, else alongside
    the current DB file. Read at call time (no import-time freeze) so
    external mutations (conftest, --db, env changes) keep working.
    """
    return os.environ.get(
        "TASK_ORCHESTRATOR_WORKSPACES",
        str(Path(db.DB_PATH).parent / "workspaces.json"),
    )


def _row_to_config(row) -> dict:
    return {
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "memory_tags": json.loads(row["memory_tags"]) if row["memory_tags"] else [],
        "description": row["description"] or "",
        "repos": json.loads(row["repos"]) if row["repos"] else [],
        "conventions": json.loads(row["conventions"]) if row["conventions"] else [],
    }


def _import_legacy_json_if_empty(conn) -> None:
    """One-shot import of the legacy workspaces.json (R-C5).

    Only runs when the `workspaces` table is empty AND the legacy file
    exists. Once any row exists (including rows created by this import),
    the table is no longer empty and this function becomes a no-op —
    there is no re-import.
    """
    count = conn.execute("SELECT COUNT(*) AS c FROM workspaces").fetchone()["c"]
    if count > 0:
        return

    path = _legacy_json_path()
    if not os.path.exists(path):
        return

    try:
        with open(path) as f:
            legacy_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load legacy workspaces config from %s: %s", path, e)
        return

    if not legacy_data:
        return

    now = _now()
    for name, cfg in legacy_data.items():
        conn.execute(
            """
            INSERT OR IGNORE INTO workspaces
                (name, tags, memory_tags, description, repos, conventions,
                 created_at, updated_at, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                json.dumps(cfg.get("tags", [])),
                json.dumps(cfg.get("memory_tags", [])),
                cfg.get("description", ""),
                json.dumps(cfg.get("repos", [])),
                json.dumps(cfg.get("conventions", [])),
                now,
                now,
                None,
                None,
            ),
        )
    conn.commit()
    logger.info("Imported %d legacy workspace(s) from %s", len(legacy_data), path)


def list_workspaces() -> dict:
    conn = db.get_connection()
    try:
        _import_legacy_json_if_empty(conn)
        rows = conn.execute("SELECT * FROM workspaces").fetchall()
        return {row["name"]: _row_to_config(row) for row in rows}
    finally:
        conn.close()


def create_workspace(
    name: str,
    tags: list[str],
    memory_tags: list[str] | None = None,
    description: str = "",
    repos: list[str] | None = None,
    conventions: list[str] | None = None,
) -> dict:
    conn = db.get_connection()
    try:
        existing = conn.execute(
            "SELECT 1 FROM workspaces WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            raise ValueError(f"Workspace '{name}' already exists")

        agent_id = _get_agent_id()
        now = _now()
        conn.execute(
            """
            INSERT INTO workspaces
                (name, tags, memory_tags, description, repos, conventions,
                 created_at, updated_at, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                json.dumps(tags),
                json.dumps(memory_tags or []),
                description,
                json.dumps(repos or []),
                json.dumps(conventions or []),
                now,
                now,
                agent_id,
                agent_id,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM workspaces WHERE name = ?", (name,)
        ).fetchone()
        return {name: _row_to_config(row)}
    finally:
        conn.close()


def update_workspace(
    name: str,
    tags: list[str] | None = None,
    memory_tags: list[str] | None = None,
    description: str | None = None,
    repos: list[str] | None = None,
    conventions: list[str] | None = None,
) -> dict:
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Workspace '{name}' not found")

        current = _row_to_config(row)
        if tags is not None:
            current["tags"] = tags
        if memory_tags is not None:
            current["memory_tags"] = memory_tags
        if description is not None:
            current["description"] = description
        if repos is not None:
            current["repos"] = repos
        if conventions is not None:
            current["conventions"] = conventions

        agent_id = _get_agent_id()
        conn.execute(
            """
            UPDATE workspaces
            SET tags = ?, memory_tags = ?, description = ?, repos = ?,
                conventions = ?, updated_at = ?, updated_by = ?
            WHERE name = ?
            """,
            (
                json.dumps(current["tags"]),
                json.dumps(current["memory_tags"]),
                current["description"],
                json.dumps(current["repos"]),
                json.dumps(current["conventions"]),
                _now(),
                agent_id,
                name,
            ),
        )
        conn.commit()
        return {name: current}
    finally:
        conn.close()


def delete_workspace(name: str) -> dict:
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM workspaces WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Workspace '{name}' not found")
        conn.execute("DELETE FROM workspaces WHERE name = ?", (name,))
        conn.commit()
        return {"deleted": name}
    finally:
        conn.close()


def get_workspace_tags(name: str) -> list[str] | None:
    """Get tags for a workspace. Returns None if workspace not found."""
    conn = db.get_connection()
    try:
        _import_legacy_json_if_empty(conn)
        row = conn.execute(
            "SELECT tags FROM workspaces WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["tags"]) if row["tags"] else []
    finally:
        conn.close()


def get_workspace_config(name: str) -> dict | None:
    """Get full workspace config. Returns None if workspace not found."""
    conn = db.get_connection()
    try:
        _import_legacy_json_if_empty(conn)
        row = conn.execute(
            "SELECT * FROM workspaces WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_config(row)
    finally:
        conn.close()
