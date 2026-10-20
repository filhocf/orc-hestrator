"""RED — /api/arcs deve devolver só ARCOS: raízes que têm filhos.

Achado em produção (20/out, visto na tela por Claudio): a página Arcos listava 29
nós achatados — sub-arcos ao lado do arco-pai e até uma tarefa no meio.

Causa: `list_arcs` filtrava só pela tag `arc`, sem exigir `parent_id IS NULL`. A
tag está poluída: há tarefas filhas marcadas com `arc` (ex.: "Fix #1352").

Regra (Claudio, 20/out): hierarquia é FILIAÇÃO, não etiqueta.
  arco     = raiz que tem filhos        -> aparece em /api/arcs
  sub-arco = filho que tem filhos       -> aparece aninhado sob o pai
  tarefa   = item sem filhos            -> nunca aparece em Arcos

O frontend já sabe montar a árvore (ArcNode expande via /api/arcs/{id}); o
defeito é só do endpoint. Estes testes travam o contrato.
"""

import pytest
from fastapi.testclient import TestClient

from task_orchestrator import engine
from task_orchestrator.web.api import build_rest_app


@pytest.fixture()
def client():
    c = TestClient(build_rest_app())
    engine.create_user(
        username="arcstester",
        password="fixture-pw",
        role="admin",
        created_by="user:system",
    )
    resp = c.post(
        "/api/auth/login",
        json={"username": "arcstester", "password": "fixture-pw"},
    )
    assert resp.status_code == 200, resp.text
    return c


def _titulos(payload: dict) -> list[str]:
    return [i["title"] for i in payload["items"]]


def test_only_roots_with_children_are_listed(client):
    """Tag `arc` numa raiz sem filhos NÃO basta: arco é quem tem filho."""
    arco = engine.create_item(title="ARCO DE TESTE", tags="arc")
    engine.create_item(title="fatia do arco", parent_id=arco["id"])

    solto = engine.create_item(title="TAREFA RAIZ COM TAG ARC", tags="arc")
    assert engine.get_children(solto["id"]) == []

    resposta = client.get("/api/arcs")
    assert resposta.status_code == 200
    titulos = _titulos(resposta.json())

    assert "ARCO DE TESTE" in titulos
    assert "TAREFA RAIZ COM TAG ARC" not in titulos, (
        "raiz sem filhos não é arco, mesmo com a tag `arc` (regra de filiação)"
    )
    assert resposta.json()["total"] == len(titulos)


def test_subarc_never_appears_at_top_level(client):
    """Sub-arco (filho que tem filhos) aparece sob o pai, nunca na lista raiz."""
    arco = engine.create_item(title="ARCO PAI", tags="arc")
    sub = engine.create_item(title="SUB-ARCO FILHO", parent_id=arco["id"], tags="arc")
    engine.create_item(title="fatia do sub-arco", parent_id=sub["id"])

    raiz = _titulos(client.get("/api/arcs").json())
    assert "ARCO PAI" in raiz
    assert "SUB-ARCO FILHO" not in raiz

    filhos = client.get(f"/api/arcs/{arco['id']}").json()["children"]
    assert [c["title"] for c in filhos] == ["SUB-ARCO FILHO"]

    # A UI precisa saber que o filho é arco ANTES de expandir (ícone da árvore).
    assert filhos[0]["has_children"] in (1, True)


def test_deep_tree_keeps_only_the_root_at_top(client):
    """Três níveis: só o arco-raiz aparece na listagem; neto também não vaza."""
    arco = engine.create_item(title="ARCO RAIZ 3N", tags="arc")
    sub = engine.create_item(title="NIVEL 2", parent_id=arco["id"], tags="arc")
    neto = engine.create_item(title="NIVEL 3", parent_id=sub["id"], tags="arc")
    engine.create_item(title="fatia", parent_id=neto["id"])

    raiz = _titulos(client.get("/api/arcs").json())
    assert "ARCO RAIZ 3N" in raiz
    assert "NIVEL 2" not in raiz
    assert "NIVEL 3" not in raiz

    nivel2 = client.get(f"/api/arcs/{arco['id']}").json()["children"]
    assert [c["title"] for c in nivel2] == ["NIVEL 2"]

    nivel3 = client.get(f"/api/arcs/{sub['id']}").json()["children"]
    assert [c["title"] for c in nivel3] == ["NIVEL 3"]
