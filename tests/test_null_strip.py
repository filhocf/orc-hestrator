"""RED/GREEN — `_row_to_dict` sem campos nulos (fatia D da 2.2.0).

Spec: docs/specs/SPEC-evolucao-2.2.0.md §5 (R-D1..R-D4, AC-D1..D4).

Medido no board real antes de implementar: `get_context` full −15,8% e
`query_items(50)` −13,3%. Vale o risco, que é a UI: campo que a tela lê e some
vira tela quebrada. Por isso o strip vale para LISTAS (onde está o volume) e
`get_item` mantém as chaves completas — quem precisa distinguir "ausente" de
"nulo" tem onde buscar.
"""

from __future__ import annotations

import json

from task_orchestrator import engine, server

# Regra final (spec §5, R-D1a/b/c — decisão fechada, não reabrir):
#   ESTRUTURAIS: identidade e proveniência do item, sempre presentes mesmo que
#   o valor no banco seja NULL. `test_http_api` fixa esse contrato desde antes
#   da fatia — um consumidor que perde `created_by` não distingue item de stub.
#   OPCIONAIS: informação acessória; ausente é mais barato que nulo e o leitor
#   deve tratar como falsy (R-D3).
#   `summary`/`description` não entram em nenhuma das listas: o schema dá
#   default '' e string vazia é valor, não nulo.
STRUCTURAL = (
    "id",
    "title",
    "status",
    "priority",
    "created_at",
    "created_by",
    "updated_at",
)
OPTIONAL_NULLABLE = (
    "due_at",
    "parent_id",
    "status_label",
    "previous_status",
    "complexity",
    "schedule",
    "metadata",
    "properties",
)


def _first_item(payload) -> dict:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if isinstance(data, dict):
        data = data.get("items") or data.get("active") or []
    return data[0]


def _assert_rule(row: dict) -> None:
    """Uma asserção, três usos: estruturais presentes, opcionais nulas ausentes."""
    missing_structural = [k for k in STRUCTURAL if k not in row]
    assert missing_structural == [], f"estruturais ausentes: {missing_structural}"
    present_optional = [k for k in OPTIONAL_NULLABLE if k in row and row[k] is None]
    assert present_optional == [], (
        f"opcionais nulas ainda presentes: {present_optional}"
    )


def test_query_items_keeps_structural_and_drops_null_optionals():
    engine.create_item("sem campos opcionais")
    row = _first_item(server.query_items(operation="list", limit=5))
    assert row["created_by"] is None  # NULL no banco, chave presente
    _assert_rule(row)


def test_query_items_keeps_fields_that_have_values():
    engine.create_item("com prazo", due_at="2026-12-01T00:00:00+00:00")
    data = json.loads(server.query_items(operation="list", limit=5))
    items = data["items"] if isinstance(data, dict) else data
    assert any(i.get("due_at") == "2026-12-01T00:00:00+00:00" for i in items)


def test_get_context_lists_omit_nulls():
    ativo = engine.create_item("ativo")
    engine.advance_item(
        ativo["id"], "start"
    )  # sem isto `active` fica vazio e o teste não prova nada
    ctx = json.loads(server.get_context())
    assert ctx["active"], "lista active vazia: o teste não provaria nada"
    for row in ctx["active"]:
        _assert_rule(row)


def test_get_blocked_items_omits_nulls():
    assert json.loads(server.get_blocked_items()) == []  # nada bloqueado
    a = engine.create_item("a")
    b = engine.create_item("b")
    engine.add_dependency(a["id"], b["id"])
    blocked = json.loads(server.get_blocked_items())
    assert blocked, "lista blocked vazia: o teste não provaria nada"
    for row in blocked:
        _assert_rule(row)


def test_get_item_keeps_the_complete_shape():
    """R-D4: leitura de um item só continua com todas as chaves."""
    created = engine.create_item("completo")
    item = json.loads(server.query_items(operation="get", item_id=created["id"]))
    assert "due_at" in item and item["due_at"] is None
    assert "summary" in item


def test_control_keys_survive_the_strip():
    """R-D2: paginação e contagem não podem desaparecer quando valem zero/None."""
    engine.create_item("x")
    page = json.loads(server.query_items(operation="list", limit=1, compact=True))
    assert {"items", "count", "has_more", "next_offset"} <= set(page)
    assert page["has_more"] is False and page["next_offset"] is None
    ctx = json.loads(server.get_context(verbosity="compact"))
    assert {"active_total", "blocked_total", "stale_total", "stale_limit"} <= set(ctx)
