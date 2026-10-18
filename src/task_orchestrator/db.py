"""SQLite database layer for persistent work item storage."""

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level flag: True if FTS5 is available and initialized
fts_available = False

# F7 (R3): ORC_DB is the primary variable; TASK_ORCHESTRATOR_DB remains a
# fallback with a single deprecation warning per process. The new default is
# ~/.orc/tasks.db (README), with a continuity guard for the pre-rename path.
DEFAULT_DB_PATH = Path.home() / ".orc" / "tasks.db"
_LEGACY_DEFAULT_DB_PATH = Path.home() / ".task-orchestrator" / "tasks.db"

_legacy_db_warned = False
_continuity_warned = False


def resolve_db_path() -> Path:
    """Resolve the database path: ORC_DB -> TASK_ORCHESTRATOR_DB -> default.

    ORC_DB is primary (F7 R3); the legacy variable still works as a fallback
    and emits a single deprecation warning per process. External mutations of
    the module attribute ``DB_PATH`` continue to take precedence at
    connection time — ``get_connection`` reads the attribute on every call.
    """
    global _legacy_db_warned
    orc_db = os.environ.get("ORC_DB")
    if orc_db:
        return Path(orc_db)
    legacy_db = os.environ.get("TASK_ORCHESTRATOR_DB")
    if legacy_db:
        if not _legacy_db_warned:
            _legacy_db_warned = True
            logger.warning("TASK_ORCHESTRATOR_DB is deprecated; use ORC_DB instead.")
        return Path(legacy_db)
    return DEFAULT_DB_PATH


def _effective_db_path() -> str:
    """Continuity guard for the pre-rename default (F7, decision of 18/out),
    evaluated at first real database use (G5 P2-1) — not at module load.

    When no env var is set, the DB_PATH attribute is still the untouched
    new default, the new default does not exist but the legacy database
    does: keep using the legacy one and warn once (naming ORC_DB) instead
    of silently starting an empty database. External mutations of
    ``DB_PATH`` (conftest, UI ``--db``) take precedence: the guard only
    applies to the untouched default.
    """
    global _continuity_warned
    if (
        not os.environ.get("ORC_DB")
        and not os.environ.get("TASK_ORCHESTRATOR_DB")
        and Path(DB_PATH) == DEFAULT_DB_PATH
        and not DEFAULT_DB_PATH.exists()
        and _LEGACY_DEFAULT_DB_PATH.exists()
    ):
        if not _continuity_warned:
            _continuity_warned = True
            logger.warning(
                "Continuity: legacy database found at %s — using it instead "
                "of the new default %s. Set ORC_DB to choose explicitly.",
                _LEGACY_DEFAULT_DB_PATH,
                DEFAULT_DB_PATH,
            )
        return str(_LEGACY_DEFAULT_DB_PATH)
    return DB_PATH


# Initial value (str, as before F7): the pure resolved path, no continuity
# side effects at import (G5 P2-1). conftest and the test suite keep working
# by mutating this attribute directly; get_connection reads the attribute on
# every call and applies the continuity guard at first use.
DB_PATH = str(resolve_db_path())

SCHEMA = """
CREATE TABLE IF NOT EXISTS work_items (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES work_items(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queue',
    status_label TEXT DEFAULT NULL,
    previous_status TEXT DEFAULT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    complexity INTEGER DEFAULT NULL,
    item_type TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    metadata TEXT DEFAULT NULL,
    properties TEXT DEFAULT NULL,
    role_changed_at TEXT DEFAULT NULL,
    due_at TEXT DEFAULT NULL,
    schedule TEXT DEFAULT NULL,
    next_run_at TEXT DEFAULT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'queue',
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(item_id, key)
);

CREATE TABLE IF NOT EXISTS dependencies (
    id TEXT PRIMARY KEY,
    from_id TEXT NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    to_id TEXT NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    dep_type TEXT NOT NULL DEFAULT 'blocks',
    unblock_at TEXT NOT NULL DEFAULT 'done',
    created_at TEXT NOT NULL,
    UNIQUE(from_id, to_id)
);

-- Session registry incorporation (v1.4.0): central presence (triple identity).
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    agent_id TEXT DEFAULT NULL,
    hostname TEXT NOT NULL,
    pid INTEGER NOT NULL DEFAULT 0,
    cli TEXT NOT NULL DEFAULT '',
    theme TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL
);

-- Unified claim table (work_item | resource); owner = session_id (triple via JOIN).
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    subject_type TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    agent_id TEXT DEFAULT NULL,
    resource_type TEXT DEFAULT NULL,
    claimed_at TEXT NOT NULL,
    expires_at TEXT DEFAULT NULL,
    UNIQUE(subject_type, subject_ref)
);

-- User authentication + RBAC (F1, SPEC-user-auth-rbac). username unique
-- case-insensitively (COLLATE NOCASE); password_hash is 'scrypt$n$r$p$salt$hash'.
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    created_by TEXT DEFAULT NULL,
    last_login_at TEXT DEFAULT NULL
);

-- Server-side sessions: cookie carries the opaque token, table stores its hash.
CREATE TABLE IF NOT EXISTS user_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_parent ON work_items(parent_id);
CREATE INDEX IF NOT EXISTS idx_items_status ON work_items(status);
CREATE INDEX IF NOT EXISTS idx_notes_item ON notes(item_id);
CREATE INDEX IF NOT EXISTS idx_deps_from ON dependencies(from_id);
CREATE INDEX IF NOT EXISTS idx_deps_to ON dependencies(to_id);
CREATE INDEX IF NOT EXISTS idx_due_at ON work_items(due_at) WHERE due_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_hostname ON sessions(hostname);
CREATE INDEX IF NOT EXISTS idx_sessions_heartbeat ON sessions(heartbeat_at);
CREATE INDEX IF NOT EXISTS idx_claims_subject ON claims(subject_type, subject_ref);
CREATE INDEX IF NOT EXISTS idx_claims_session ON claims(session_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at);
"""

MIGRATIONS = [
    (
        "previous_status",
        "ALTER TABLE work_items ADD COLUMN previous_status TEXT DEFAULT NULL",
    ),
    (
        "unblock_at",
        "ALTER TABLE dependencies ADD COLUMN unblock_at TEXT NOT NULL DEFAULT 'done'",
    ),
    ("summary", "ALTER TABLE work_items ADD COLUMN summary TEXT DEFAULT ''"),
    (
        "status_label",
        "ALTER TABLE work_items ADD COLUMN status_label TEXT DEFAULT NULL",
    ),
    ("complexity", "ALTER TABLE work_items ADD COLUMN complexity INTEGER DEFAULT NULL"),
    ("metadata", "ALTER TABLE work_items ADD COLUMN metadata TEXT DEFAULT NULL"),
    ("properties", "ALTER TABLE work_items ADD COLUMN properties TEXT DEFAULT NULL"),
    (
        "role_changed_at",
        "ALTER TABLE work_items ADD COLUMN role_changed_at TEXT DEFAULT NULL",
    ),
    ("due_at", "ALTER TABLE work_items ADD COLUMN due_at TEXT DEFAULT NULL"),
    ("schedule", "ALTER TABLE work_items ADD COLUMN schedule TEXT DEFAULT NULL"),
    ("next_run_at", "ALTER TABLE work_items ADD COLUMN next_run_at TEXT DEFAULT NULL"),
    # Agent ID attribution columns
    (
        "work_items_created_by",
        "ALTER TABLE work_items ADD COLUMN created_by TEXT DEFAULT NULL",
    ),
    (
        "work_items_updated_by",
        "ALTER TABLE work_items ADD COLUMN updated_by TEXT DEFAULT NULL",
    ),
    ("notes_created_by", "ALTER TABLE notes ADD COLUMN created_by TEXT DEFAULT NULL"),
    (
        "dependencies_created_by",
        "ALTER TABLE dependencies ADD COLUMN created_by TEXT DEFAULT NULL",
    ),
    # Session registry incorporation (v1.4.0) — additive/defensive. Tables are new,
    # so SCHEMA already creates every column; these guard pre-existing partial tables.
    (
        "sessions_agent_id",
        "ALTER TABLE sessions ADD COLUMN agent_id TEXT DEFAULT NULL",
    ),
    (
        "sessions_hostname",
        "ALTER TABLE sessions ADD COLUMN hostname TEXT NOT NULL DEFAULT 'unknown'",
    ),
    (
        "sessions_cli",
        "ALTER TABLE sessions ADD COLUMN cli TEXT NOT NULL DEFAULT ''",
    ),
    (
        "claims_agent_id",
        "ALTER TABLE claims ADD COLUMN agent_id TEXT DEFAULT NULL",
    ),
    (
        "claims_resource_type",
        "ALTER TABLE claims ADD COLUMN resource_type TEXT DEFAULT NULL",
    ),
    (
        "claims_expires_at",
        "ALTER TABLE claims ADD COLUMN expires_at TEXT DEFAULT NULL",
    ),
]


def get_connection() -> sqlite3.Connection:
    path = _effective_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    _run_migrations(conn)
    _init_fts(conn)
    conn.close()


def _init_fts(conn: sqlite3.Connection):
    """Create FTS5 virtual table and sync triggers. Falls back gracefully if FTS5 unavailable."""
    global fts_available
    # Check if FTS table already exists to avoid unnecessary rebuild
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='items_fts'"
    ).fetchone()
    if exists:
        fts_available = True
        return
    try:
        conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
                id, title, description, content=work_items, content_rowid=rowid
            );

            CREATE TRIGGER IF NOT EXISTS items_fts_ai AFTER INSERT ON work_items BEGIN
                INSERT INTO items_fts(rowid, id, title, description)
                VALUES (NEW.rowid, NEW.id, NEW.title, NEW.description);
            END;

            CREATE TRIGGER IF NOT EXISTS items_fts_ad AFTER DELETE ON work_items BEGIN
                INSERT INTO items_fts(items_fts, rowid, id, title, description)
                VALUES ('delete', OLD.rowid, OLD.id, OLD.title, OLD.description);
            END;

            CREATE TRIGGER IF NOT EXISTS items_fts_au AFTER UPDATE ON work_items BEGIN
                INSERT INTO items_fts(items_fts, rowid, id, title, description)
                VALUES ('delete', OLD.rowid, OLD.id, OLD.title, OLD.description);
                INSERT INTO items_fts(rowid, id, title, description)
                VALUES (NEW.rowid, NEW.id, NEW.title, NEW.description);
            END;
        """)
        # Only rebuild on first creation to sync existing data
        conn.execute("INSERT INTO items_fts(items_fts) VALUES('rebuild')")
        conn.commit()
        fts_available = True
    except Exception:
        logger.warning("FTS5 not available — falling back to LIKE-based search")
        fts_available = False


def _run_migrations(conn: sqlite3.Connection):
    """Apply additive migrations safely."""
    for name, sql in MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
