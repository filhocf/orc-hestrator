import uuid
from datetime import UTC, datetime
from typing import ClassVar

from ..db import get_connection
from ..workspace import get_workspace_tags

VALID_STATUSES = {"queue", "work", "review", "done", "blocked", "cancelled", "archived"}


class ToolError(Exception):
    """Structured error with code, field, and message."""

    CODES: ClassVar[set[str]] = {
        "NOT_FOUND",
        "VALIDATION",
        "CONFLICT",
        "DEPENDENCY_UNSATISFIED",
        "GATE_BLOCKED",
    }

    def __init__(self, code: str, message: str, field: str = ""):
        self.code = code
        self.field = field
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict:
        d = {"error": {"code": self.code, "message": self.message}}
        if self.field:
            d["error"]["field"] = self.field
        return d


def resolve_short_id(prefix: str) -> str:
    """Resolve a 4+ char hex prefix to a full item ID."""
    if len(prefix) < 4:
        raise ToolError("VALIDATION", "Short ID must be at least 4 characters", "id")
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id FROM work_items WHERE id LIKE ?", (f"{prefix}%",)
        ).fetchall()
        if len(rows) == 0:
            raise ToolError("NOT_FOUND", f"No item matching prefix '{prefix}'", "id")
        if len(rows) > 1:
            ids = [r["id"] for r in rows]
            raise ToolError(
                "CONFLICT", f"Prefix '{prefix}' matches {len(ids)} items: {ids}", "id"
            )
        return rows[0]["id"]
    finally:
        conn.close()


TERMINAL = {"done", "cancelled", "archived"}
PRIORITIES = {"critical", "high", "medium", "low"}
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

TRANSITIONS = {
    "start": {"queue": "work", "work": "review", "review": "done"},
    "complete": {"queue": "done", "work": "done", "review": "done"},
    "block": {"queue": "blocked", "work": "blocked", "review": "blocked"},
    "cancel": {
        "queue": "cancelled",
        "work": "cancelled",
        "review": "cancelled",
        "blocked": "cancelled",
    },
    "reopen": {"done": "queue", "cancelled": "queue"},
    "archive": {"done": "archived"},
}


def _parse_dt(s: str) -> datetime:
    """Parse ISO datetime string, assuming UTC if no timezone info."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row) -> dict | None:
    return dict(row) if row else None


def _validate_priority(priority: str):
    if priority and priority not in PRIORITIES:
        raise ToolError(
            "VALIDATION",
            f"Invalid priority: {priority}. Valid: {sorted(PRIORITIES)}",
            "priority",
        )


def _validate_due_at(due_at: str | None):
    if due_at is not None:
        try:
            datetime.fromisoformat(due_at)
        except (ValueError, TypeError):
            raise ToolError(
                "VALIDATION",
                f"Invalid due_at: {due_at}. Must be ISO 8601 datetime string.",
                "due_at",
            )


def _workspace_tag_filter(workspace: str | None) -> tuple[str, list[str]]:
    """Return (SQL clause, params) to filter items by workspace tags. Empty if no workspace."""
    if not workspace:
        return "", []
    tags = get_workspace_tags(workspace)
    if tags is None:
        raise ToolError("NOT_FOUND", f"Workspace '{workspace}' not found", "workspace")
    clauses = " OR ".join("tags LIKE ?" for _ in tags)
    return f"({clauses})", [f"%{t}%" for t in tags]
