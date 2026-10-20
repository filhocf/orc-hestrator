"""RED/GREEN — import_graph deve levantar ToolError, não KeyError (G5, 2.2.0).

Fato pré-existente (não é regressão da 2.2.0), medido no review G5:
`portability.import_graph({'items':[{'ghost_field':'x'}], ...}, mode='merge')`
levanta `KeyError: 'id'` em vez de um erro estruturado. Causa:
`_sort_items_topologically` (engine/portability.py) assume `item["id"]` e roda
antes de `_insert_rows`, sem validar o payload primeiro.

Correção: validar `id` presente em cada item ANTES de ordenar e levantar
`ToolError("VALIDATION", ...)` nomeando o item ofensor e o campo ausente —
mesmo padrão já usado no resto do repo (engine/base.py).
"""

from __future__ import annotations

import pytest

from task_orchestrator.engine import portability
from task_orchestrator.engine.base import ToolError


def test_import_graph_item_without_id_raises_tool_error_not_key_error():
    payload = {
        "items": [{"ghost_field": "x"}],
        "notes": [],
        "dependencies": [],
        "workspaces": {},
    }
    with pytest.raises(ToolError) as exc_info:
        portability.import_graph(payload, mode="merge")
    err = exc_info.value
    assert err.code == "VALIDATION"
    assert err.field == "id"
    # A mensagem precisa nomear o campo ausente e dar pista de qual item é o
    # ofensor (índice, já que não há id para identificá-lo por nome).
    assert "id" in err.message
    assert "0" in err.message or "ghost_field" in err.message


def test_import_graph_second_item_without_id_is_also_caught():
    """A validação precisa cobrir TODOS os itens do batch, não só o primeiro."""
    payload = {
        "items": [
            {"id": "a", "title": "A", "status": "queue", "priority": "medium"},
            {"title": "sem id"},
        ],
        "notes": [],
        "dependencies": [],
        "workspaces": {},
    }
    with pytest.raises(ToolError) as exc_info:
        portability.import_graph(payload, mode="merge")
    assert exc_info.value.code == "VALIDATION"
    assert exc_info.value.field == "id"


def test_import_graph_well_formed_items_still_work(tmp_db):
    """Guarda de não-regressão: payload válido continua importando normalmente."""
    now = "2026-10-20T00:00:00+00:00"
    payload = {
        "items": [
            {
                "id": "ok-1",
                "title": "ok",
                "status": "queue",
                "priority": "medium",
                "created_at": now,
                "updated_at": now,
            }
        ],
        "notes": [],
        "dependencies": [],
        "workspaces": {},
    }
    result = portability.import_graph(payload, mode="merge")
    assert result["imported"] is True
    assert result["counts"]["items"] == 1
