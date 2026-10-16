"""SQLite database layer for persistent work item storage."""

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level flag: True if FTS5 is available and initialized
fts_available = False

DB_PATH = os.environ.get(
    "TASK_ORCHESTRATOR_DB",
    str(Path.home() / ".task-orchestrator" / "tasks.db"),
)

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
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
