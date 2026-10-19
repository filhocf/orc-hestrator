"""RED tests for FEAT-6b (RFC-003 C): workspaces in SQLite, not workspaces.json.

Covers:
- R-C1: workspaces table in the same SQLite file.
- R-C3: created_by/updated_by recorded via engine.base agent_id contextvar.
- R-C4: export_graph/import_graph include workspaces (merge and replace).
- R-C5: one-shot import of a legacy workspaces.json when the table is empty;
  no reimport once the table has rows.
"""

import json
import sqlite3

import pytest

from task_orchestrator import engine, workspace
from task_orchestrator.engine.base import set_agent_id


@pytest.fixture(autouse=True)
def _reset_agent_id():
    set_agent_id(None)
    yield
    set_agent_id(None)


class TestWorkspacesInDatabase:
    """R-C1: workspace data is persisted in the workspaces table, not JSON."""

    def test_create_workspace_persists_in_sqlite_table(self, tmp_db):
        workspace.create_workspace("dtp", ["mir", "rer"], description="Team DTP")

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM workspaces WHERE name = ?", ("dtp",)
        ).fetchone()
        conn.close()

        assert row is not None
        assert json.loads(row["tags"]) == ["mir", "rer"]
        assert row["description"] == "Team DTP"

    def test_delete_workspace_removes_row(self, tmp_db):
        workspace.create_workspace("dtp", ["mir"])
        workspace.delete_workspace("dtp")

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM workspaces WHERE name = ?", ("dtp",)
        ).fetchone()
        conn.close()
        assert row is None


class TestWorkspaceAuthorship:
    """R-C3: created_by/updated_by from the agent_id contextvar, verified by SQL."""

    def test_create_workspace_records_created_by(self, tmp_db):
        set_agent_id("zero")
        workspace.create_workspace("dtp", ["mir"])

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT created_by, updated_by FROM workspaces WHERE name = ?", ("dtp",)
        ).fetchone()
        conn.close()

        assert row["created_by"] == "zero"
        assert row["updated_by"] == "zero"

    def test_update_workspace_preserves_created_by_sets_updated_by(self, tmp_db):
        set_agent_id("zero")
        workspace.create_workspace("dtp", ["mir"])

        set_agent_id("tpol")
        workspace.update_workspace("dtp", description="Updated")

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT created_by, updated_by FROM workspaces WHERE name = ?", ("dtp",)
        ).fetchone()
        conn.close()

        assert row["created_by"] == "zero"
        assert row["updated_by"] == "tpol"

    def test_create_workspace_without_agent_id_is_null(self, tmp_db):
        set_agent_id(None)
        workspace.create_workspace("anon", ["x"])

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT created_by FROM workspaces WHERE name = ?", ("anon",)
        ).fetchone()
        conn.close()

        assert row["created_by"] is None


class TestExportImportWorkspaces:
    """R-C4: export_graph/import_graph carry workspaces through merge and replace."""

    def test_export_graph_includes_workspaces(self, tmp_db):
        workspace.create_workspace("dtp", ["mir", "rer"], description="Team")

        data = engine.export_graph()

        assert "workspaces" in data
        assert "dtp" in data["workspaces"]
        assert data["workspaces"]["dtp"]["tags"] == ["mir", "rer"]

    def test_import_graph_merge_restores_deleted_workspace(self, tmp_db):
        workspace.create_workspace("dtp", ["mir"])
        data = engine.export_graph()
        workspace.delete_workspace("dtp")
        assert workspace.list_workspaces() == {}

        result = engine.import_graph(data, mode="merge")

        assert result["imported"] is True
        assert "dtp" in workspace.list_workspaces()

    def test_import_graph_replace_restores_workspaces_and_clears_extra(self, tmp_db):
        workspace.create_workspace("dtp", ["mir"])
        data = engine.export_graph()

        workspace.delete_workspace("dtp")
        workspace.create_workspace("extra", ["x"])

        result = engine.import_graph(data, mode="replace")

        assert result["imported"] is True
        ws = workspace.list_workspaces()
        assert "dtp" in ws
        assert "extra" not in ws

    def test_replace_with_legacy_export_keeps_workspaces(self, tmp_db):
        """Export anterior à FEAT-6b não tem a chave `workspaces`.

        Replace não pode apagar a configuração só porque o arquivo importado é
        antigo — sem essa guarda, restaurar um backup pré-2.1.0 zeraria os
        workspaces em silêncio.
        """
        workspace.create_workspace("dtp", ["mir"], description="Team")
        legacy_export = {
            "items": [],
            "notes": [],
            "dependencies": [],
            "version": "1.3.0",
        }

        engine.import_graph(legacy_export, mode="replace")

        ws = workspace.list_workspaces()
        assert "dtp" in ws
        assert ws["dtp"]["tags"] == ["mir"]

    def test_export_import_roundtrip_preserves_full_config(self, tmp_db):
        workspace.create_workspace(
            "proj",
            tags=["api", "web"],
            memory_tags=["proj-mem"],
            description="Main project",
            repos=["~/git/proj"],
            conventions=["PEP8"],
        )
        data = engine.export_graph()
        workspace.delete_workspace("proj")

        engine.import_graph(data, mode="merge")

        ws = workspace.get_workspace_config("proj")
        assert ws["tags"] == ["api", "web"]
        assert ws["memory_tags"] == ["proj-mem"]
        assert ws["description"] == "Main project"
        assert ws["repos"] == ["~/git/proj"]
        assert ws["conventions"] == ["PEP8"]


class TestLegacyJsonOneShotImport:
    """R-C5: import workspaces.json once when the table is empty; never again."""

    def test_imports_legacy_json_when_table_empty(self, tmp_db, tmp_path, monkeypatch):
        legacy_path = tmp_path / "workspaces.json"
        legacy_path.write_text(
            json.dumps(
                {
                    "legacy-ws": {
                        "tags": ["old"],
                        "memory_tags": [],
                        "description": "From JSON",
                        "repos": [],
                        "conventions": [],
                    }
                }
            )
        )
        monkeypatch.setenv("TASK_ORCHESTRATOR_WORKSPACES", str(legacy_path))

        result = workspace.list_workspaces()

        assert "legacy-ws" in result
        assert result["legacy-ws"]["description"] == "From JSON"

    def test_does_not_reimport_once_table_has_rows(self, tmp_db, tmp_path, monkeypatch):
        legacy_path = tmp_path / "workspaces.json"
        legacy_path.write_text(json.dumps({"legacy-ws": {"tags": ["old"]}}))
        monkeypatch.setenv("TASK_ORCHESTRATOR_WORKSPACES", str(legacy_path))

        # First call triggers one-shot import; table now has >=1 row.
        workspace.list_workspaces()
        # Change the JSON file after the import — a second load must NOT
        # reimport, because the table is no longer empty.
        legacy_path.write_text(
            json.dumps(
                {
                    "legacy-ws": {"tags": ["new-should-not-appear"]},
                    "second-ws": {"tags": ["also-should-not-appear"]},
                }
            )
        )

        result = workspace.list_workspaces()

        # Only the originally-imported value is present; the edited file's
        # new workspace was never imported, and the original tags were not
        # overwritten by the edited file.
        assert result["legacy-ws"]["tags"] == ["old"]
        assert "second-ws" not in result

    def test_does_not_import_when_table_already_has_rows(
        self, tmp_db, tmp_path, monkeypatch
    ):
        legacy_path = tmp_path / "workspaces.json"
        legacy_path.write_text(json.dumps({"legacy-ws": {"tags": ["old"]}}))
        monkeypatch.setenv("TASK_ORCHESTRATOR_WORKSPACES", str(legacy_path))

        # Table already has a row created directly via the DB API — the
        # table is non-empty from the start, so the legacy file must never
        # be imported, even though it exists and has not been read yet.
        workspace.create_workspace("native", ["x"])

        result = workspace.list_workspaces()

        assert "native" in result
        assert "legacy-ws" not in result
