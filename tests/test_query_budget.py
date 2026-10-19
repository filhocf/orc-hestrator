"""Orçamento de consultas do `get_context` (FEAT-1b do RFC-003).

O RFC-003 mede payload; este arquivo mede o outro custo, que o G5 da FEAT-1
expôs: `get_context` avaliava a fila item a item (`_get_unsatisfied_blockers`
por linha), o que dava 115 consultas de dependência num board de 64 itens.
Latência e carga no SQLite escalavam com o tamanho da FILA, não com o trabalho
que o agente pediu.

A guarda é um teto de consultas, não um tempo: tempo varia com a máquina e vira
teste instável. Teto generoso (o caminho atual faz 10-12 com 40 itens na fila);
o que ele impede é a volta do N+1, que faria 40+.
"""

from __future__ import annotations

import pytest

from task_orchestrator import db, engine
from task_orchestrator.engine import queries

QUEUE_ITEMS = 40
QUERY_BUDGET = 20


class _SpyConn:
    def __init__(self, real, log: list[str]):
        self._real = real
        self._log = log

    def execute(self, sql, params=()):
        self._log.append(" ".join(sql.split()))
        return self._real.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture()
def full_queue():
    """Fila grande o bastante para o N+1 aparecer se voltar."""
    ids = []
    for i in range(QUEUE_ITEMS):
        item = engine.create_item(f"Fila {i}", priority="medium")
        ids.append(item["id"])
    # Uma dependência satisfeita e uma insatisfeita: exercita o filtro de blockers.
    engine.add_dependency(ids[0], ids[1])
    engine.advance_item(ids[0], "start")
    return ids


@pytest.mark.parametrize("verbosity", ["full", "compact"])
def test_get_context_stays_within_the_query_budget(monkeypatch, full_queue, verbosity):
    log: list[str] = []
    real = db.get_connection
    monkeypatch.setattr(queries, "get_connection", lambda: _SpyConn(real(), log))

    engine.get_context(verbosity=verbosity)

    assert len(log) <= QUERY_BUDGET, (
        f"{verbosity} fez {len(log)} consultas para {QUEUE_ITEMS} itens na fila "
        f"(teto {QUERY_BUDGET}) — o N+1 de blockers voltou"
    )


def test_blockers_are_fetched_in_one_query(monkeypatch, full_queue):
    """O N+1 era exatamente isto: uma consulta por item para checar dependências."""
    log: list[str] = []
    real = db.get_connection
    monkeypatch.setattr(queries, "get_connection", lambda: _SpyConn(real(), log))

    engine.get_context(verbosity="compact")

    dep_queries = [q for q in log if "FROM dependencies" in q]
    assert len(dep_queries) <= 2, (
        f"{len(dep_queries)} consultas de dependência para {QUEUE_ITEMS} itens: "
        "blockers deveriam ser buscados em lote"
    )
