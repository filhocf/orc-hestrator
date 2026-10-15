"""Workflow engine — status transitions, dependency checks, queries.

Status flow: queue → work → review → done
Any non-terminal status can go to: blocked (via block trigger) → resume → previous status
Terminal statuses: done, cancelled
"""

# Import from base module
# Import from archive module
from .archive import archive_items, archive_list, archive_stats
from .base import (
    PRIORITIES,
    PRIORITY_ORDER,
    TERMINAL,
    TRANSITIONS,
    VALID_STATUSES,
    ToolError,
    _parse_dt,
    get_agent_id,
    reset_agent_id,
    resolve_short_id,
    set_agent_id,
)

# Import from dependencies module
from .dependencies import (
    add_dependency,
    add_dependency_pattern,
    get_dependencies,
    query_dependencies_bfs,
    remove_dependency,
)

# Import from items module
from .items import (
    create_item,
    create_items_batch,
    delete_item,
    delete_items_batch,
    get_ancestors,
    get_children,
    get_item,
    query_items,
    update_item,
)

# Import from metrics module
from .metrics import get_metrics, get_project_graph_metrics

# Import from notes module
from .notes import delete_note, get_notes, upsert_note

# Import from portability module
from .portability import export_graph, import_graph

# Import from queries module
from .queries import get_blocked_items, get_context, get_next_item

# Import from transitions module
from .transitions import advance_item, advance_items_batch, get_next_status

# Import from trees module
from .trees import complete_tree, create_work_tree

# Import from workspace_view module
from .workspace_view import get_execution_stack, get_workspace_context

__all__ = [
    "PRIORITIES",
    "PRIORITY_ORDER",
    "TERMINAL",
    "TRANSITIONS",
    "VALID_STATUSES",
    # Base
    "ToolError",
    "_parse_dt",
    # Dependencies
    "add_dependency",
    "add_dependency_pattern",
    # Transitions
    "advance_item",
    "advance_items_batch",
    # Archive
    "archive_items",
    "archive_list",
    "archive_stats",
    "complete_tree",
    # Items
    "create_item",
    "create_items_batch",
    # Trees
    "create_work_tree",
    "delete_item",
    "delete_items_batch",
    "delete_note",
    # Portability
    "export_graph",
    "get_agent_id",
    "get_ancestors",
    "get_blocked_items",
    "get_children",
    "get_context",
    "get_dependencies",
    "get_execution_stack",
    "get_item",
    # Metrics
    "get_metrics",
    # Queries
    "get_next_item",
    "get_next_status",
    "get_notes",
    "get_project_graph_metrics",
    # Workspace View
    "get_workspace_context",
    "import_graph",
    "query_dependencies_bfs",
    "query_items",
    "remove_dependency",
    "reset_agent_id",
    "resolve_short_id",
    # Agent ID
    "set_agent_id",
    "update_item",
    # Notes
    "upsert_note",
]
