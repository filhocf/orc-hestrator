"""RED/GREEN — exceção do null-strip para a vista de DETALHE (G5, 2.2.0).

Decisão de desenho já tomada (não reabrir aqui): `get_context(item_id=...)`
devolve `item`/`children`/`notes`/`blockers` com TODAS as chaves, inclusive
nulas — mesma razão de R-D4 (`query_items(operation='get')`): é leitura de UM
item, não payload de lista, e quem consome precisa distinguir "ausente" de
"nulo".

Este teste TRAVA essa exceção: se algum dia alguém "uniformizar" o strip e
passar a aplicar `drop_nulls=True` também no detalhe, esta suíte quebra aqui
primeiro — antes de uma UI perder um campo que ela lia.

Nota para a orquestradora (G5): a spec (docs/specs/SPEC-evolucao-2.2.0.md §5)
documenta R-D4 só para `get_item`/`query_items(operation='get')`. Falta um
R-D4b explícito cobrindo `get_context(item_id=...)` — mesma regra, superfície
diferente. Este arquivo não edita a spec; só prova o comportamento no código.
"""

from __future__ import annotations

import json

from task_orchestrator import server
from task_orchestrator.engine import dependencies, items, queries
from task_orchestrator.engine import notes as notes_engine

# Mesmas listas de tests/test_null_strip.py (não reimportadas para não
# acoplar os dois arquivos; os dois precisam continuar corretos de forma
# independente).
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


def test_get_context_detail_keeps_null_optional_keys_on_item():
    """item do detalhe mantém chaves opcionais nulas (NÃO aplica drop_nulls)."""
    created = items.create_item("detalhe sem opcionais")
    ctx = queries.get_context(item_id=created["id"])
    item = ctx["item"]
    # Prova positiva e direta: campos que o banco deixa NULL por default devem
    # continuar presentes no payload do detalhe.
    for key in ("due_at", "status_label", "complexity", "metadata", "properties"):
        assert key in item and item[key] is None, (
            f"detalhe de item único deve manter {key!r} nula (R-D4); ausente ou removida"
        )


def test_get_context_detail_keeps_null_optional_keys_on_children():
    """children do detalhe mantêm chaves opcionais nulas — mesma exceção do item."""
    parent = items.create_item("pai")
    items.create_item("filho sem opcionais", parent_id=parent["id"])
    ctx = queries.get_context(item_id=parent["id"])
    assert ctx["children"], "children vazio: o teste não provaria nada"
    child = ctx["children"][0]
    for key in ("due_at", "status_label", "complexity", "metadata", "properties"):
        assert key in child and child[key] is None, (
            f"children do detalhe deve manter {key!r} nula (R-D4b); ausente ou removida"
        )


def test_get_context_detail_keeps_null_optional_keys_on_notes():
    """notes do detalhe mantêm chaves opcionais nulas — mesma exceção do item."""
    item = items.create_item("com nota")
    notes_engine.upsert_note(item["id"], "req", "corpo", role="queue")
    ctx = queries.get_context(item_id=item["id"])
    assert ctx["notes"], "notes vazio: o teste não provaria nada"
    note = ctx["notes"][0]
    # `created_by` é a opcional nula garantida aqui (nenhum agent_id no
    # contexto de teste); se o strip chegasse às notes do detalhe, a chave
    # desapareceria.
    assert "created_by" in note and note["created_by"] is None


def test_query_items_and_get_blocked_items_do_not_keep_this_exception():
    """Contraste explícito: a exceção é só do DETALHE. Listas continuam
    aplicando o strip — query_items e get_blocked_items NÃO mantêm as
    opcionais nulas (R-D1/R-D3), diferente do que este arquivo prova para
    get_context(item_id=...).
    """
    items.create_item("para lista")
    data = json.loads(server.query_items(operation="list", limit=5))
    rows = data["items"] if isinstance(data, dict) else data
    assert rows, "lista vazia: o teste não provaria nada"
    for row in rows:
        present_optional = [k for k in OPTIONAL_NULLABLE if k in row and row[k] is None]
        assert present_optional == [], (
            "query_items(list) deve APLICAR o strip — opcionais nulas "
            f"não podem sobreviver (diferente do detalhe): {present_optional}"
        )

    a = items.create_item("a")
    b = items.create_item("b")
    dependencies.add_dependency(b["id"], a["id"])
    blocked = json.loads(server.get_blocked_items())
    assert blocked, "blocked vazio: o teste não provaria nada"
    row = blocked[0]
    present_optional = [k for k in OPTIONAL_NULLABLE if k in row and row[k] is None]
    assert present_optional == [], (
        "get_blocked_items deve APLICAR o strip na raiz — opcionais nulas "
        f"não podem sobreviver (diferente do detalhe): {present_optional}"
    )
    for blocker in row["blocked_by"]:
        present_optional = [
            k for k in OPTIONAL_NULLABLE if k in blocker and blocker[k] is None
        ]
        assert present_optional == [], (
            "get_blocked_items deve APLICAR o strip no aninhado blocked_by "
            f"também (fix G5-1) — opcionais nulas não podem sobreviver: {present_optional}"
        )
