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

# Import from claims module (unified claim)
from .claims import claim, conflicts, get_claim_for, release

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
    children_with_counts,
    count_arc_roots,
    create_item,
    create_items_batch,
    delete_item,
    delete_items_batch,
    get_ancestors,
    get_children,
    get_item,
    list_arc_roots,
    project_items,
    query_items,
    update_item,
)

# Import from metrics module
from .metrics import get_metrics, get_project_graph_metrics

# Import from notes module
from .notes import delete_note, get_notes, upsert_note

# Import from portability module
from .portability import export_graph, import_graph

# Import from presence module (session registry — central presence)
from .presence import (
    end as presence_end,
)
from .presence import (
    heartbeat as presence_heartbeat,
)
from .presence import (
    list_active as presence_list,
)
from .presence import (
    reap as presence_reap,
)
from .presence import (
    register as presence_register,
)

# Import from queries module
from .queries import get_blocked_items, get_context, get_next_item

# Import from transitions module
from .transitions import advance_item, advance_items_batch, get_next_status

# Import from trees module
from .trees import complete_tree, create_work_tree

# Import from users module (F1 — auth + RBAC)
from .users import (
    create_session,
    create_user,
    delete_session,
    get_user,
    hash_password,
    list_users,
    lookup_session,
    prune_expired,
    seed_admin,
    set_user_active,
    touch_last_login,
    verify_credentials,
    verify_password,
)

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
    "children_with_counts",
    # Claims (unified claim)
    "claim",
    "complete_tree",
    "conflicts",
    "count_arc_roots",
    # Items
    "create_item",
    "create_items_batch",
    # Users (F1 — auth + RBAC)
    "create_session",
    "create_user",
    # Trees
    "create_work_tree",
    "delete_item",
    "delete_items_batch",
    "delete_note",
    "delete_session",
    # Portability
    "export_graph",
    "get_agent_id",
    "get_ancestors",
    "get_blocked_items",
    "get_children",
    "get_claim_for",
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
    "get_user",
    # Workspace View
    "get_workspace_context",
    "hash_password",
    "import_graph",
    "list_arc_roots",
    "list_users",
    "lookup_session",
    # Presence (session registry)
    "presence_end",
    "presence_heartbeat",
    "presence_list",
    "presence_reap",
    "presence_register",
    # Items — projeção (RFC-003 FEAT-2)
    "project_items",
    "prune_expired",
    "query_dependencies_bfs",
    "query_items",
    "release",
    "remove_dependency",
    "reset_agent_id",
    "resolve_short_id",
    "seed_admin",
    # Agent ID
    "set_agent_id",
    "set_user_active",
    "touch_last_login",
    "update_item",
    # Notes
    "upsert_note",
    "verify_credentials",
    "verify_password",
]
