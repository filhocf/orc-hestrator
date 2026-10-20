"""Projeção de campos e modo compact nas listas (FEAT-2 do RFC-003).

Contrato (docs/specs/SPEC-economia-contexto-2.1.0.md, R-D1..R-D6):
`fields` e `compact` são OPT-IN. Sem eles, `engine.query_items` devolve a linha
completa — `web/api.py` chama o engine direto e alimenta a UI React, então mudar
o default aqui quebraria a tela.

Fatia D da 2.2.0 (SPEC-evolucao-2.2.0.md §5): "linha completa" passou a significar
**todas as chaves não nulas + as estruturais** (R-D1a). A projeção continua
desligada por default; o que mudou é que chave opcional nula não é mais enviada.
`get_item` segue devolvendo tudo (R-D4), e é ele que serve de referência para
provar que o strip só removeu o que devia.

O modo compact devolve a página explícita ({items, count, has_more, next_offset})
em vez da lista crua: sem `has_more` o agente infere "acabou" por
`len(items) < limit`, que é falso quando o total é múltiplo do limite.
"""

from __future__ import annotations

import json

import pytest

from task_orchestrator import engine, server
from task_orchestrator.engine.base import STRUCTURAL_KEYS, ToolError
from task_orchestrator.engine.items import COMPACT_FIELDS, ITEM_FIELDS

# 165, não 150: o teto do RFC foi estimado sem contar que cada acento em JSON
# escapado custa 6 chars. Com ensure_ascii=False o item medido no board real é
# 163; abaixo disso só truncando título a ponto de perder identificação.
PER_ITEM_BUDGET = 165


@pytest.fixture()
def items():
    return [
        engine.create_item(
            f"Item {i}",
            description="descrição " * 20,
            priority=["critical", "high", "medium", "low"][i % 4],
        )
        for i in range(5)
    ]


def _call(**kwargs) -> dict | list:
    return json.loads(server.query_items(**kwargs))


# --- default preservado ----------------------------------------------------


def test_default_still_returns_the_whole_row(items):
    """Fatia D: o default não projeta nada — devolve a linha inteira, menos as
    chaves opcionais nulas (R-D1b). A referência é `get_item`, que mantém tudo."""
    rows = engine.query_items()
    assert rows
    row = rows[0]
    full = engine.get_item(row["id"])
    assert full is not None
    expected = {k for k, v in full.items() if v is not None} | set(STRUCTURAL_KEYS)
    assert set(row) == expected, (
        f"sobra: {set(row) - expected} | falta: {expected - set(row)}"
    )
    assert expected <= set(ITEM_FIELDS), "o strip não pode inventar chave nova"
    # o que sobrevive ao strip é subconjunto do schema, e nada estrutural sumiu
    assert set(STRUCTURAL_KEYS) <= set(row)


def test_item_fields_matches_the_real_schema(items):
    """A constante não pode divergir das colunas que _row_to_dict devolve."""
    real = set(engine.get_item(items[0]["id"]))
    assert set(ITEM_FIELDS) == real, f"divergência: {set(ITEM_FIELDS) ^ real}"


def test_mcp_without_compact_still_returns_a_plain_list(items):
    payload = _call()
    assert isinstance(payload, list)
    assert payload and "description" in payload[0]


# --- projeção -------------------------------------------------------------


def test_fields_projects_in_the_requested_order(items):
    rows = engine.query_items(fields="status,title,id")
    assert rows
    for row in rows:
        assert list(row) == ["status", "title", "id"]


def test_unknown_field_is_a_structured_error(items):
    with pytest.raises(ToolError) as exc:
        engine.query_items(fields="id,naoexiste")
    assert exc.value.field == "fields"
    assert "naoexiste" in exc.value.message


def test_unknown_field_through_mcp_is_an_error_payload(items):
    payload = _call(fields="id,naoexiste")
    assert payload["error"]["field"] == "fields"
    assert payload["error"]["code"] == "VALIDATION"


# --- compact --------------------------------------------------------------


def test_compact_keeps_each_item_under_the_budget(items):
    payload = _call(compact=True)
    for row in payload["items"]:
        size = len(json.dumps(row, ensure_ascii=False))
        assert size <= PER_ITEM_BUDGET, f"item com {size} chars: {row}"
    assert list(payload["items"][0]) == list(COMPACT_FIELDS)


def test_compact_reports_the_page_explicitly(items):
    payload = _call(compact=True, limit=2)
    assert payload["count"] == 2
    assert payload["has_more"] is True
    assert payload["next_offset"] == 2


def test_last_page_has_no_next_offset(items):
    payload = _call(compact=True, limit=2, offset=4)
    assert payload["count"] == 1
    assert payload["has_more"] is False
    assert payload["next_offset"] is None


def test_exact_multiple_does_not_claim_more_pages(items):
    """5 itens com limit=5: a página cheia é a última — len==limit não prova nada."""
    payload = _call(compact=True, limit=5)
    assert payload["count"] == 5
    assert payload["has_more"] is False


# --- get_blocked_items ----------------------------------------------------


def test_blocked_items_accept_projection(items):
    blocker = engine.create_item("Bloqueador")
    engine.add_dependency(blocker["id"], items[0]["id"])

    compact = json.loads(server.get_blocked_items(compact=True))
    assert compact
    for row in compact:
        assert list(row) == list(COMPACT_FIELDS)

    default = json.loads(server.get_blocked_items())
    assert "description" in default[0]
