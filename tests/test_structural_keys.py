"""RED antes do fix — contrato de chaves ESTRUTURAIS no null-strip (fatia D).

Spec: docs/specs/SPEC-evolucao-2.2.0.md §5 (R-D1..R-D4, AC-D1..D4).

A fatia D introduziu `_row_to_dict(row, drop_nulls=True)` em `engine/base.py`:
quando verdadeiro, omite TODA chave cujo valor seja None, inclusive chaves
ESTRUTURAIS que o contrato vigente (tests/test_http_api.py,
test_items_populated_returns_items_with_created_by) exige sempre presentes —
mesmo quando o valor é None.

Decisao de desenho (nao reabrir aqui):
  * Estruturais (sempre presentes, mesmo com valor None):
      id, title, status, priority, created_at, created_by, updated_at
  * Opcionais (omitidas quando None):
      due_at, parent_id, status_label, previous_status, complexity,
      schedule, metadata, properties
  * Chaves de controle de envelope (count, has_more, next_offset, total,
    *_total) continuam sempre presentes — ja e o caso, nao tocado aqui.
  * get_item mantem todas as chaves (R-D4) — nao exercido por este arquivo.
  * summary/description NAO entram na lista de opcionais: o schema da
    default '', string vazia nao e nulo.

Este arquivo insere o item via SQL direto (bypassando engine.create_item, que
nao aceita created_by/due_at/parent_id como None explicito de forma simples
para forcar o NULL) contra o banco temporario de `tmp_db`/`engine_db`
(conftest.py), nunca contra ORC_DB real.
"""

from __future__ import annotations

import json
import uuid

from task_orchestrator import db, server

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


def _insert_item_with_nulls(item_id: str, title: str) -> None:
    """Insere uma work_items row com created_by, due_at e parent_id NULL.

    SQL direto contra o banco de `tmp_db` (via `db.get_connection()`), nao via
    engine.create_item — precisamos garantir NULL explicito em colunas que a
    API de alto nivel preenche com default nao-nulo ou nao aceita None direto.
    """
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO work_items (
                id, parent_id, title, description, summary, status,
                priority, created_by, updated_by, created_at, updated_at
            ) VALUES (?, NULL, ?, '', '', 'queue', 'medium', NULL, NULL, ?, ?)
            """,
            (item_id, title, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()


def _first_item(payload) -> dict:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if isinstance(data, dict):
        data = data.get("items") or []
    return data[0]


def test_structural_keys_present_with_none_value():
    """R-D1/estrutural: created_by (NULL) tem que aparecer na lista, nao so em get_item."""
    item_id = str(uuid.uuid4())
    _insert_item_with_nulls(item_id, "estrutural com nulls")
    data = json.loads(server.query_items(operation="list", limit=10))
    items = data["items"] if isinstance(data, dict) else data
    row = next(i for i in items if i["id"] == item_id)
    missing = [k for k in STRUCTURAL if k not in row]
    assert missing == [], f"chaves estruturais ausentes: {missing}"
    assert row["created_by"] is None


def test_optional_keys_omitted_when_none():
    """Chave opcional (due_at/parent_id) continua omitida quando o valor e None."""
    item_id = str(uuid.uuid4())
    _insert_item_with_nulls(item_id, "opcionais nulos")
    data = json.loads(server.query_items(operation="list", limit=10))
    items = data["items"] if isinstance(data, dict) else data
    row = next(i for i in items if i["id"] == item_id)
    present = [k for k in ("due_at", "parent_id") if k in row]
    assert present == [], f"opcionais ainda presentes com valor None: {present}"


def test_optional_keys_present_when_they_have_a_value():
    """Chave opcional com valor real continua presente (nao e strip incondicional)."""
    from task_orchestrator import engine

    engine.create_item("com prazo", due_at="2026-12-01T00:00:00+00:00")
    data = json.loads(server.query_items(operation="list", limit=10))
    items = data["items"] if isinstance(data, dict) else data
    assert any(i.get("due_at") == "2026-12-01T00:00:00+00:00" for i in items)
