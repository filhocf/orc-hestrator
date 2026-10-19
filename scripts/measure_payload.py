"""Régua de payload do Orc (RFC-003) — bytes por chamada, numa placa fixa.

Por que existe: os critérios de aceite do RFC-003 são números ("≤1.500 chars",
"−45%", "≤150 por item"). Sem uma placa determinística e uma medição
reprodutível, nenhum deles é verificável — e otimização vira opinião.

A placa imita a produção, não o caso feliz: 64 itens em 8 arcos, 12 em `work`
com notas de fase, itens velhos em `queue`, dependência bloqueando, e **um arco
com descrição de 5.000 caracteres** (o caso que estoura o contexto de verdade).

Uso:
    .venv/bin/python scripts/measure_payload.py            # tabela
    .venv/bin/python scripts/measure_payload.py --json     # JSON puro
    .venv/bin/python scripts/measure_payload.py --tool get_context

Mede o mesmo que o cliente paga: `TextContent` + `structuredContent` quando
existir. Um número menor aqui é um número menor na conta de crédito.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import statistics
import sys
import tempfile
from datetime import UTC, datetime, timedelta

# Banco temporário ANTES de importar o pacote: db.DB_PATH é resolvido no import.
_DB_DIR = tempfile.mkdtemp(prefix="orc-bench-")
os.environ["ORC_DB"] = os.path.join(_DB_DIR, "bench.db")

from task_orchestrator import db, engine
from task_orchestrator.server import mcp

ARCS, CHILDREN, IN_WORK = 8, 8, 12
BIG_DESCRIPTION = 5_000


def calls(sample_id: str) -> list[tuple[str, dict]]:
    """O que uma sessão de agente realmente chama, na ordem em que chama."""
    return [
        ("get_context", {}),
        ("query_items", {"operation": "list"}),
        ("query_items", {"operation": "list", "limit": 10}),
        ("query_items", {"operation": "list", "status": "work"}),
        ("get_blocked_items", {}),
        ("get_next_item", {}),
        ("get_execution_stack", {}),
        ("get_metrics", {}),
        ("query_notes", {"item_id": sample_id, "include_body": False}),
        ("query_notes", {"item_id": sample_id, "include_body": True}),
    ]


def build_plate() -> None:
    """Cria a placa sintética num banco limpo (idempotente por execução)."""
    db.init_db()
    old = datetime.now(UTC) - timedelta(days=30)
    priorities = ["critical", "high", "medium", "low"]
    created = 0

    for a in range(ARCS):
        arc = engine.create_item(
            f"ARC-{a}: arco de teste",
            description="x" * BIG_DESCRIPTION
            if a == 0
            else f"Arco {a} com descrição normal.",
            priority=priorities[a % 4],
            tags="arc,bench",
        )
        engine.advance_item(arc["id"], "start")
        engine.advance_item(arc["id"], "complete")  # arcos não contam no WIP

        for c in range(CHILDREN):
            item = engine.create_item(
                f"Filho {a}.{c}",
                description=f"Descrição realista do item {a}.{c}. " * 6,
                parent_id=arc["id"],
                priority=priorities[c % 4],
                due_at=(old + timedelta(days=c)).isoformat() if c % 5 == 0 else None,
            )
            engine.upsert_note(item["id"], "queue", "nota de fila", role="queue")
            created += 1

    # 12 itens em `work`, com nota de fase e um deles velho o bastante para stale.
    work = engine.query_items(status="queue", limit=IN_WORK)
    for i, item in enumerate(work):
        engine.advance_item(item["id"], "start")
        engine.upsert_note(item["id"], "work", "em andamento", role="work")
        if i < 3:  # envelhece o item para exercitar o ramo de stale
            conn = db.get_connection()
            try:
                conn.execute(
                    "UPDATE work_items SET updated_at=? WHERE id=?",
                    (old.isoformat(), item["id"]),
                )
                conn.commit()
            finally:
                conn.close()

    # Bloqueio real: item em `queue` esperando item em `work` (não-done) —
    # é o caso que `get_blocked_items` enxerga.
    waiting = engine.query_items(status="queue", limit=1)
    running = engine.query_items(status="work", limit=1)
    if waiting and running:
        engine.add_dependency(running[0]["id"], waiting[0]["id"])  # from bloqueia to

    print(
        f"placa: {created} filhos + {ARCS} arcos, {IN_WORK} em work, "
        f"descrição máx {BIG_DESCRIPTION} chars",
        file=sys.stderr,
    )


def _split(result) -> tuple[str, dict | None]:
    """Normaliza o retorno de `call_tool` (tupla com structured ou lista)."""
    if isinstance(result, tuple):
        content, structured = result
        text = "".join(b.text for b in content if getattr(b, "text", None))
        return text, structured
    return "".join(b.text for b in result if getattr(b, "text", None)), None


async def measure(sample_id: str) -> tuple[list[dict], list[str]]:
    rows = []
    texts: list[str] = []
    for name, args in calls(sample_id):
        text, structured = _split(await mcp.call_tool(name, args))
        texts.append(text)
        text_b = len(text.encode())
        struct_b = (
            len(json.dumps(structured, ensure_ascii=False).encode())
            if structured
            else 0
        )
        items = _item_count(text)
        rows.append(
            {
                "tool": name,
                "args": args,
                "text_bytes": text_b,
                "structured_bytes": struct_b,
                "total_bytes": text_b + struct_b,
                "items": items,
                "bytes_per_item": round(text_b / items, 1) if items else None,
                "est_tokens": round((text_b + struct_b) / 4),
            }
        )
    return rows, texts


def _item_count(text: str) -> int:
    """Nº de itens no payload, quando ele é uma lista JSON."""
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return 0
    if isinstance(payload, list):
        return len(payload)
    return 1 if isinstance(payload, dict) and payload else 0


# --- caracterização do contrato de leitura (RFC-003, invariante 2) ----------
#
# O payload medido não é estável entre execuções: a placa é criada a cada vez,
# então todo item nasce com um `uuid4` novo, todo `created_at`/`updated_at`
# carrega o relógio do momento, `get_metrics` devolve `lead_time_avg_seconds`
# com microssegundos variáveis e `throughput_per_week[].week` muda de semana
# para semana.
#
# A caracterização precisa medir o CONTRATO (quais campos vêm, em que forma,
# com que texto), não o relógio. Por isso o payload é normalizado de forma
# ESTRUTURAL: parse do JSON, substituição dos valores voláteis por placeholders
# e re-serialização determinística (`separators=(",", ":")`).
#
# As duas medidas não se confundem, e isso é deliberado:
#   * `chars` desta caracterização = tamanho do payload NORMALIZADO — serve para
#     detectar mudança de forma/estrutura, com hash estável entre execuções;
#   * tamanho real por chamada = a tabela e o `--json` desta régua, que NÃO
#     normalizam nada. É esse número que o RFC-003 cita em bytes e tokens
#     (bytes/4, a mesma conversão do RFC).
# Tentar preservar comprimento em todos os campos seria pior: o float de
# `lead_time_avg_seconds` muda de 11 para 21 caracteres conforme o valor, e um
# placeholder de largura fixa mentiria sobre o tamanho de qualquer jeito.
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_TS_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)
_WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")

# Campos cujo valor é relógio ou medição de tempo de execução, não contrato.
VOLATILE_KEYS = {"lead_time_avg_seconds", "week"}


def _normalize_scalar(value):
    if isinstance(value, str):
        if _UUID_RE.fullmatch(value):
            return "<uuid>"
        if _WEEK_RE.fullmatch(value):
            return "<week>"
        if _TS_RE.fullmatch(value):
            return "<timestamp>"
    return value


def _normalize_tree(node):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key in VOLATILE_KEYS:
                out[key] = f"<{key}>"
            else:
                out[key] = _normalize_tree(value)
        return out
    if isinstance(node, list):
        return [_normalize_tree(v) for v in node]
    return _normalize_scalar(node)


def normalize_payload(text: str) -> str:
    """Normaliza valores voláteis e devolve texto determinístico."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # Não é JSON: cai para a substituição textual, preservando o resto.
        text = _UUID_RE.sub("<uuid>", text)
        return _TS_RE.sub("<timestamp>", text)
    return json.dumps(
        _normalize_tree(parsed), ensure_ascii=False, separators=(",", ":")
    )


def digest_rows(rows: list[dict], texts: list[str]) -> list[dict]:
    """chars + sha256 do payload normalizado, por chamada (base da caracterização)."""
    out = []
    for i, (row, text) in enumerate(zip(rows, texts, strict=True), start=1):
        norm = normalize_payload(text)
        args = json.loads(
            normalize_payload(json.dumps(row["args"], ensure_ascii=False))
        )
        out.append(
            {
                "key": f"{i:02d}-{row['tool']}",
                "tool": row["tool"],
                "args": args,
                "chars": len(norm),
                "sha256": hashlib.sha256(norm.encode()).hexdigest(),
                "est_tokens": round(len(norm) / 4),
            }
        )
    return out


def render(rows: list[dict]) -> None:
    head = (
        f"{'tool':<20}{'args':<34}{'texto':>9}{'total':>9}"
        f"{'itens':>7}{'b/item':>9}{'~tok':>8}"
    )
    print(head)
    print("-" * len(head))
    for r in rows:
        args = ",".join(f"{k}={v}" for k, v in r["args"].items())[:33]
        print(
            f"{r['tool']:<20}{args:<34}{r['text_bytes']:>9}"
            f"{r['total_bytes']:>9}{r['items']:>7}"
            f"{r['bytes_per_item'] or 0:>9}{r['est_tokens']:>8}"
        )
    total = sum(r["total_bytes"] for r in rows)
    median = statistics.median(r["total_bytes"] for r in rows)
    print("-" * len(head))
    print(
        f"\nTOTAL das {len(rows)} chamadas: {total} b (~{round(total / 4)} tokens) · mediana {median:.0f} b"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="saída JSON pura")
    parser.add_argument("--tool", help="mede só uma tool")
    parser.add_argument(
        "--digest",
        action="store_true",
        help="digests normalizados (chars + sha256) — base da caracterização",
    )
    parser.add_argument(
        "--dump",
        metavar="DIR",
        help="grava os payloads normalizados em DIR (usado pela caracterização)",
    )
    opts = parser.parse_args()

    build_plate()
    sample = engine.query_items(status="work", limit=1)
    if not sample:
        sys.exit("placa vazia: nenhum item em work")
    rows, texts = asyncio.run(measure(sample[0]["id"]))
    if opts.tool:
        keep = [
            (r, t) for r, t in zip(rows, texts, strict=True) if r["tool"] == opts.tool
        ]
        if not keep:
            sys.exit(f"tool desconhecida: {opts.tool}")
        rows = [r for r, _ in keep]
        texts = [t for _, t in keep]

    if opts.dump:
        from pathlib import Path

        out = Path(opts.dump)
        out.mkdir(parents=True, exist_ok=True)
        for entry, text in zip(digest_rows(rows, texts), texts, strict=True):
            (out / f"{entry['key']}.txt").write_text(normalize_payload(text), "utf-8")

    if opts.digest:
        print(json.dumps(digest_rows(rows, texts), indent=2, ensure_ascii=False))
    elif opts.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        render(rows)


if __name__ == "__main__":
    main()
