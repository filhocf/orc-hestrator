"""RED — `_insert_rows` deriva colunas de `rows[0]` e perde dados.

Spec: docs/specs/SPEC-correcao-insert-rows-2.1.1.md (R-A1..A6, AC-1..AC-6),
absorvida pela 2.2.0.

O defeito, em uma frase: se a PRIMEIRA linha do lote não traz uma coluna que as
outras trazem, a coluna desaparece do INSERT inteiro e o valor das demais é
descartado — sem erro, sem log, com `import_graph` devolvendo sucesso.

A entrada é JSON externo: o usuário pode editar o arquivo ou concatenar dois
exports. Homogeneidade do export não é garantia sobre o que chega.
"""

from __future__ import annotations

import json

from task_orchestrator import db, engine
from task_orchestrator.engine import portability

STAMP = {
    "created_at": "2026-10-20T10:00:00+00:00",
    "updated_at": "2026-10-20T10:00:00+00:00",
}


def _insert(table: str, rows: list[dict]) -> None:
    """Insere e comita — sem commit a leitura numa conexão nova veria nada."""
    conn = db.get_connection()
    try:
        portability._insert_rows(conn, table, rows)
        conn.commit()
    finally:
        conn.close()


def _rows(table: str) -> list[dict]:
    conn = db.get_connection()
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
    finally:
        conn.close()


def _item(item_id: str, title: str, **extra) -> dict:
    row = {
        "id": item_id,
        "title": title,
        "status": "queue",
        "priority": "medium",
        **STAMP,
    }
    row.update(extra)
    return row


def test_work_items_preserves_value_when_first_row_lacks_the_column():
    """AC-1/AC-2: a linha 0 sem `summary` não pode apagar o `summary` da linha 1."""
    _insert(
        "work_items",
        [
            _item("a1", "sem resumo"),
            _item("b2", "com resumo", summary="valor que importa"),
        ],
    )

    by_id = {r["id"]: r for r in _rows("work_items")}
    assert by_id["b2"]["summary"] == "valor que importa"  # hoje: NULL
    assert by_id["a1"]["summary"] is None  # ausência vira NULL só nesta linha


def test_notes_preserves_body_when_first_note_lacks_it():
    """AC-6: mesmo defeito em `notes` — `body` da segunda nota não pode cair no default."""
    _insert("work_items", [_item("i1", "item")])
    _insert(
        "notes",
        [
            {
                "id": "n1",
                "item_id": "i1",
                "key": "a",
                "created_at": "x",
                "updated_at": "x",
            },
            {
                "id": "n2",
                "item_id": "i1",
                "key": "b",
                "body": "corpo real",
                "created_at": "x",
                "updated_at": "x",
            },
        ],
    )

    by_id = {r["id"]: r for r in _rows("notes")}
    assert by_id["n2"]["body"] == "corpo real"  # hoje: '' (default)


def test_dependencies_preserves_unblock_at_when_first_row_lacks_it():
    """AC-6: idem em `dependencies` — `unblock_at` da segunda não pode cair no default."""
    _insert("work_items", [_item(f"d{i}", f"i{i}") for i in (1, 2, 3)])
    _insert(
        "dependencies",
        [
            {"id": "dep1", "from_id": "d1", "to_id": "d3", "created_at": "x"},
            {
                "id": "dep2",
                "from_id": "d2",
                "to_id": "d3",
                "unblock_at": "review",
                "created_at": "x",
            },
        ],
    )

    by_id = {r["id"]: r for r in _rows("dependencies")}
    assert by_id["dep2"]["unblock_at"] == "review"  # hoje: 'done'


def test_unknown_key_is_ignored():
    """AC-4: a tabela é a autoridade; chave estranha não vira erro nem coluna."""
    _insert("work_items", [_item("x1", "t", campo_que_nao_existe="ignorar")])
    assert [r["id"] for r in _rows("work_items")] == ["x1"]


def test_homogeneous_batch_is_unchanged():
    """AC-5: o caminho que já funciona não pode mudar."""
    _insert("work_items", [_item(f"h{i}", "t") for i in range(3)])
    got = _rows("work_items")
    assert len(got) == 3
    assert {r["title"] for r in got} == {"t"}


def test_import_graph_end_to_end_preserves_heterogeneous_payload():
    """AC-1 via caminho público: o dado tem de sobreviver ao import_graph."""
    result = engine.import_graph(
        {
            "items": [
                _item("e1", "primeiro"),
                _item("e2", "segundo", summary="sobrevive"),
            ],
            "notes": [],
            "dependencies": [],
            "workspaces": {},
        },
        mode="merge",
    )
    assert "error" not in result
    conn = db.get_connection()
    try:
        assert (
            conn.execute("SELECT summary FROM work_items WHERE id='e2'").fetchone()[0]
            == "sobrevive"
        )
    finally:
        conn.close()


def test_json_string_from_external_file_still_works():
    """A entrada real é JSON: o teste passa pelo parser, não só por dicts."""
    data = json.loads(
        json.dumps(
            {
                "items": [_item("j1", "p"), _item("j2", "s", summary="via json")],
                "notes": [],
                "dependencies": [],
                "workspaces": {},
            }
        )
    )
    engine.import_graph(data, mode="merge")
    conn = db.get_connection()
    try:
        assert (
            conn.execute("SELECT summary FROM work_items WHERE id='j2'").fetchone()[0]
            == "via json"
        )
    finally:
        conn.close()
