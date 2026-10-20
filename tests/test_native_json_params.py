"""Fatia C da 2.2.0 — parâmetros nativos em vez de `*_json`.

Spec: docs/specs/SPEC-evolucao-2.2.0.md §4 (R-C1..R-C4, AC-C1..AC-C3).

O que muda para quem usa: em vez de serializar e escapar (`items_json='[{"..."}]'`),
o agente passa a estrutura direto. A string JSON continua aceita — nenhum cliente
existente quebra. Valor que não é nem estrutura nem JSON válido devolve erro
estruturado **nomeando o parâmetro**, em vez de estourar um `JSONDecodeError` cru.

Nota de processo: os testes desta fatia foram escritos DEPOIS do código (falha
minha no gate). A prova de mordida está em `test_prova_de_mordida_*`, que reverte
o comportamento e exige falha — sem isso, o verde não significaria nada.
"""

from __future__ import annotations

import json

import pytest

from task_orchestrator import server
from task_orchestrator.engine import ToolError


def _ok(raw: str) -> dict | list:
    data = json.loads(raw)
    if isinstance(data, dict) and data.get("error"):
        raise AssertionError(f"erro inesperado: {data}")
    return data


def test_manage_items_accepts_native_list():
    raw = server.manage_items(
        operation="create",
        items_json=[{"title": "nativo 1"}, {"title": "nativo 2"}],
    )
    assert len(_ok(raw)["items"]) == 2


def test_manage_items_still_accepts_json_string():
    raw = server.manage_items(
        operation="create", items_json=json.dumps([{"title": "string 1"}])
    )
    assert len(_ok(raw)["items"]) == 1


def test_manage_items_delete_accepts_native_ids():
    created = _ok(
        server.manage_items(operation="create", items_json=[{"title": "apagar"}])
    )
    raw = server.manage_items(operation="delete", ids_json=[created["items"][0]["id"]])
    result = _ok(raw)
    assert "error" not in result


def test_advance_item_accepts_native_transitions():
    a = _ok(server.manage_items(operation="create", items_json=[{"title": "t1"}]))[
        "items"
    ][0]
    b = _ok(server.manage_items(operation="create", items_json=[{"title": "t2"}]))[
        "items"
    ][0]
    raw = server.advance_item(
        transitions_json=[
            {"item_id": a["id"], "trigger": "start"},
            {"item_id": b["id"], "trigger": "start"},
        ]
    )
    result = _ok(raw)
    assert result["summary"]["succeeded"] == 2


def test_create_work_tree_accepts_native_children_and_deps():
    raw = server.create_work_tree(
        root_title="raiz",
        children_json=[{"ref": "c1", "title": "filho"}],
        deps_json=[],
    )
    assert _ok(raw)["root"]["title"] == "raiz"


def test_import_graph_accepts_native_dict():
    raw = server.import_graph(
        data_json={"items": [], "notes": [], "dependencies": [], "workspaces": {}}
    )
    assert "error" not in _ok(raw)


def test_conflicts_accepts_native_subjects():
    session = _ok(server.agent_register(cli="pytest"))["session_id"]
    raw = server.conflicts(
        subjects_json=[["work_item", "nao-existe"]], session_id=session
    )
    assert isinstance(_ok(raw), (list, dict))


def test_invalid_payload_names_the_parameter():
    """AC-C3: erro estruturado com o nome do parâmetro, não JSONDecodeError cru."""
    with pytest.raises(ToolError) as exc:
        server._json_arg("{nao-e-json", "items_json")
    assert exc.value.field == "items_json"


def test_wrong_shape_is_rejected_with_the_expected_type():
    with pytest.raises(ToolError) as exc:
        server._json_arg({"a": 1}, "items_json")
    assert "list" in str(exc.value)


def test_empty_string_keeps_historical_behaviour():
    assert server._json_arg("", "items_json") == []
    assert server._json_arg("", "data_json", dict) == {}
