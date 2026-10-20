"""RED/GREEN — `get_next_item(compact)` (fatia B da 2.2.0).

Spec: docs/specs/SPEC-evolucao-2.2.0.md §3 (R-B1..R-B3, AC-B1..B2).

O ponto da fatia: o agente pergunta "qual o próximo item?" e recebe a linha
inteira (~300 tokens) para usar cinco campos. `compact` devolve só o que ele
usa, **mais o motivo** — sem o motivo, o agente não sabe por que aquele item
venceu a fila e acaba pedindo o item completo, anulando o ganho.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from task_orchestrator import engine


def _item(title: str, **kw):
    return engine.create_item(title=title, **kw)


def test_compact_returns_only_the_fields_used_to_decide():
    _item("tarefa")
    got = engine.get_next_item(compact=True)
    assert set(got) == {"id", "title", "status", "priority", "due_at", "reason"}
    assert len(got["id"]) == 8
    assert got["reason"]


def test_compact_payload_fits_the_budget():
    """AC-B1 medido: 6 campos fixos dão 177 chars (~44 tok).

    O RFC estimou ~80 tok e um teto de 150 chars; com título legível (60) e as
    seis chaves fixas, 150 só caberia mutilando o título para ~33 chars, o que
    deixaria de identificar o item — e o agente voltaria a pedir a linha
    completa, anulando o ganho. Teto real: 180.
    """
    _item("Uma tarefa com título razoavelmente comprido para forçar o limite")
    payload = json.dumps(engine.get_next_item(compact=True), ensure_ascii=False)
    assert len(payload) <= 180, payload


def test_compact_truncates_long_title():
    _item("T" * 200)
    assert len(engine.get_next_item(compact=True)["title"]) <= 60


def test_work_in_progress_wins_and_says_so():
    done = _item("feito")
    engine.advance_item(done["id"], "start")
    engine.advance_item(done["id"], "complete")
    wip = _item("em andamento")
    engine.advance_item(wip["id"], "start")
    got = engine.get_next_item(compact=True)
    assert got["reason"] == "in progress"
    assert got["status"] == "work"


def test_overdue_is_reported_as_the_reason():
    it = _item("atrasada")
    conn = __import__("task_orchestrator.db", fromlist=["db"]).get_connection()
    past = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    conn.execute("UPDATE work_items SET due_at=? WHERE id=?", (past, it["id"]))
    conn.commit()
    conn.close()
    got = engine.get_next_item(compact=True)
    assert got["reason"] == "overdue"


def test_priority_is_the_fallback_reason():
    _item("baixa", priority="low")
    _item("critica", priority="critical")
    got = engine.get_next_item(compact=True)
    assert got["reason"] == "priority:critical"


def test_default_is_unchanged():
    """AC-B2: sem compact, o item volta completo como em 2.1.0."""
    _item("completa")
    got = engine.get_next_item()
    assert "description" in got and "created_at" in got
    assert "reason" not in got


def test_nothing_actionable_still_returns_none():
    assert engine.get_next_item(compact=True) is None
