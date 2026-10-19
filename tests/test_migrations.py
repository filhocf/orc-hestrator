"""Robustez das migrações de schema (db.py).

Duas garantias que o boot do serviço precisa ter:

1. Falha de migração que NÃO seja "coluna já existe" derruba o boot. O código
   anterior engolia qualquer `OperationalError` — um `database is locked` com
   vários agentes em WAL deixava a coluna sem criar e o erro só aparecia muito
   depois, no meio de uma sessão, como campo faltando no payload.
2. A versão do schema fica registrada (`PRAGMA user_version`), então dá para
   ordenar migrações no futuro em vez de depender só de idempotência.
"""

from __future__ import annotations

import sqlite3

import pytest

from task_orchestrator import db


def test_new_database_stamps_the_schema_version(tmp_path):
    conn = sqlite3.connect(tmp_path / "v.db")
    try:
        conn.executescript(db.SCHEMA)
        db._run_migrations(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    finally:
        conn.close()


def test_running_twice_is_idempotent(tmp_path):
    conn = sqlite3.connect(tmp_path / "v.db")
    try:
        conn.executescript(db.SCHEMA)
        db._run_migrations(conn)
        db._run_migrations(conn)  # todas as colunas já existem
        assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    finally:
        conn.close()


def test_duplicate_column_is_tolerated(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "v.db")
    try:
        conn.executescript(db.SCHEMA)
        monkeypatch.setattr(
            db, "MIGRATIONS", [("dup", "ALTER TABLE work_items ADD COLUMN title TEXT")]
        )
        db._run_migrations(conn)  # não pode levantar
    finally:
        conn.close()


def test_other_operational_errors_are_raised(tmp_path, monkeypatch):
    """`no such table` é bug de schema, não migração já aplicada."""
    conn = sqlite3.connect(tmp_path / "v.db")
    try:
        conn.executescript(db.SCHEMA)
        monkeypatch.setattr(
            db,
            "MIGRATIONS",
            [("broken", "ALTER TABLE tabela_que_nao_existe ADD COLUMN x TEXT")],
        )
        with pytest.raises(sqlite3.OperationalError):
            db._run_migrations(conn)
    finally:
        conn.close()


def test_locked_database_does_not_pass_silently(tmp_path, monkeypatch):
    """O caso real: outro agente segurando o banco durante o boot."""
    conn = sqlite3.connect(tmp_path / "v.db")
    try:
        conn.executescript(db.SCHEMA)
    finally:
        conn.close()

    holder = sqlite3.connect(tmp_path / "v.db", timeout=0)
    try:
        holder.execute("BEGIN EXCLUSIVE")
        other = sqlite3.connect(tmp_path / "v.db", timeout=0)
        try:
            monkeypatch.setattr(
                db,
                "MIGRATIONS",
                [("new_col", "ALTER TABLE work_items ADD COLUMN nunca TEXT")],
            )
            with pytest.raises(sqlite3.OperationalError):
                db._run_migrations(other)
        finally:
            other.close()
    finally:
        holder.rollback()
        holder.close()
