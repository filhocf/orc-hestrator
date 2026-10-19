"""FEAT-1 do RFC-003 — `get_context(verbosity)` e `LIMIT` em `stale_items`.

RED: estes testes descrevem o contrato de `docs/specs/SPEC-economia-contexto-2.1.0.md`
(R-B1..R-B7) antes da implementação. O default NÃO muda (opt-in, decisão do
Claudio em 19/out): sem o parâmetro, o payload continua sendo o de 2.0.1 — e a
caracterização `tests/test_reading_contract.py` é quem vigia isso byte a byte.

Sobre o id no modo compacto: UUID completo custa 36 caracteres por item e
sozinho estoura o teto de 1.500 do AC-B1 com 20 itens. O compacto devolve o
prefixo de 8 caracteres, que já é aceito nas chamadas (`resolve_short_id` aceita
4+), e `stale_total`/`stale_limit` deixam o truncamento visível.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from task_orchestrator import db, engine, server
from task_orchestrator.engine import queries

SHORT_ID = 8
COMPACT_BUDGET = 1_500
STALE_LIMIT = 10


def _age(item_id: str, days: int) -> None:
    conn = db.get_connection()
    try:
        stamp = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        conn.execute("UPDATE work_items SET updated_at=? WHERE id=?", (stamp, item_id))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def plate():
    """Placa com o que estoura o contexto: work ativo, fila velha e arcos."""
    items = {"work": [], "stale": [], "done": []}
    for i in range(12):
        item = engine.create_item(
            f"Item em andamento {i}",
            description="Descrição longa do item em andamento. " * 6,
            priority=["critical", "high", "medium", "low"][i % 4],
        )
        engine.advance_item(item["id"], "start")
        items["work"].append(item["id"])

    for i in range(25):  # fila envelhecida: 25 stale, acima do limite de 10
        item = engine.create_item(f"Item velho {i}", priority="medium")
        _age(item["id"], 30)
        items["stale"].append(item["id"])

    for i in range(5):
        item = engine.create_item(f"Item concluído {i}", priority="low")
        engine.advance_item(item["id"], "start")
        engine.advance_item(item["id"], "complete")
        items["done"].append(item["id"])
    return items


def _ctx(**kwargs) -> dict:
    return json.loads(server.get_context(**kwargs))


# --- R-B1 / R-B6: o default não muda ---------------------------------------


def test_default_equals_full_and_keeps_every_key(plate):
    default = _ctx()
    assert default == _ctx(verbosity="full")
    assert {
        "counts",
        "active",
        "blocked",
        "recent_completed",
        "next_item",
        "stale_items",
        "due_soon",
        "overdue",
        "scheduled_upcoming",
    } <= set(default)


def test_full_still_carries_the_whole_row(plate):
    """`full` é a visão de humano/depuração: não pode virar compacto por dentro."""
    active = _ctx(verbosity="full")["active"]
    assert active, "placa deveria ter itens em work"
    assert "description" in active[0]
    assert len(active[0]["description"]) > 200


# --- R-B2: valor inválido é erro estruturado -------------------------------


def test_invalid_verbosity_is_a_structured_error(plate):
    payload = _ctx(verbosity="verbose")
    assert "error" in payload, payload
    assert payload["error"]["field"] == "verbosity"
    assert payload["error"]["code"] == "VALIDATION"


# --- R-B3 / R-B4: forma e orçamento do compacto ----------------------------


def test_compact_fits_the_budget(plate):
    payload = _ctx(verbosity="compact")
    size = len(json.dumps(payload, ensure_ascii=False))
    assert size <= COMPACT_BUDGET, f"compact devolveu {size} chars (teto {COMPACT_BUDGET})"


def test_compact_shape_is_projected(plate):
    payload = _ctx(verbosity="compact")
    assert set(payload) >= {
        "counts",
        "next_item",
        "active",
        "blocked",
        "stale",
        "stale_total",
        "stale_limit",
    }
    assert payload["stale_limit"] == STALE_LIMIT
    assert len(payload["stale"]) <= STALE_LIMIT

    for row in payload["active"]:
        assert len(row) == 5, f"item ativo deveria ter 5 campos: {row}"
        assert len(row[0]) == SHORT_ID, "compact usa id curto (8 chars)"

    next_item = payload["next_item"]
    if next_item:
        assert set(next_item) == {"id", "title", "priority"}


def test_compact_reports_the_total_behind_the_limit(plate):
    """Truncar sem dizer o total é esconder impedimento — R-B4."""
    payload = _ctx(verbosity="compact")
    assert payload["stale_total"] == 25
    assert len(payload["stale"]) == STALE_LIMIT


# --- R-B5: standard acrescenta descrição truncada --------------------------


def test_standard_truncates_descriptions(plate):
    payload = _ctx(verbosity="standard")
    active = payload["active"]
    assert active
    assert any("description" in row for row in active if isinstance(row, dict))
    for row in active:
        if isinstance(row, dict) and row.get("description"):
            assert len(row["description"]) <= 200


# --- R-B7: o limite é do SQL, não do Python --------------------------------


class _SpyConn:
    def __init__(self, real, log: list[str]):
        self._real = real
        self._log = log

    def execute(self, sql, params=()):
        self._log.append(" ".join(sql.split()))
        return self._real.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_stale_items_are_limited_in_sql(monkeypatch, plate):
    """`SELECT *` de toda a fila para filtrar em Python é o custo que o RFC ataca."""
    log: list[str] = []
    real = db.get_connection
    monkeypatch.setattr(queries, "get_connection", lambda: _SpyConn(real(), log))

    _ctx(verbosity="compact")

    stale_sql = [q for q in log if "status IN ('queue','work')" in q or "status IN (?, ?)" in q]
    if not stale_sql:
        stale_sql = [q for q in log if "'queue'" in q and "'work'" in q]
    assert stale_sql, f"nenhuma consulta de stale encontrada em {len(log)} queries"
    assert any("LIMIT" in q.upper() for q in stale_sql), (
        "a consulta de stale_items não tem LIMIT — o limite está sendo aplicado em Python"
    )
