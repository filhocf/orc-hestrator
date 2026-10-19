"""A régua do RFC-003 tem que funcionar, senão os números do RFC não valem.

Executa `scripts/measure_payload.py --json` num subprocesso (é assim que o
humano e o CI a usam) e valida a **estrutura** do relatório. Sem números
absolutos de bytes: qualquer mudança de formato quebra um assert mágico e
transforma o teste em ruído.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "measure_payload.py"


@pytest.fixture(scope="module")
def report() -> list[dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, f"harness falhou:\n{proc.stderr[-2000:]}"
    return json.loads(proc.stdout)


def test_covers_the_calls_a_session_makes(report):
    tools = {row["tool"] for row in report}
    assert {"get_context", "query_items", "get_next_item", "get_metrics"} <= tools
    assert len(report) >= 8, "o relatório deve cobrir as chamadas de rotina"


def test_every_row_carries_a_measurement(report):
    for row in report:
        assert row["text_bytes"] > 0, f"{row['tool']} sem payload medido"
        assert row["total_bytes"] >= row["text_bytes"]
        assert row["est_tokens"] == round(row["total_bytes"] / 4)


def test_the_two_board_reads_dominate_the_cost(report):
    """Medido na placa: `query_items` default (50 itens) pesa mais que
    `get_context`. Os dois juntos são o custo de "onde eu estou" — se
    deixarem de dominar, ou o board encolheu ou a régua quebrou."""
    top3 = [r["tool"] for r in sorted(report, key=lambda r: -r["total_bytes"])[:3]]
    assert {"get_context", "query_items"} <= set(top3), f"top 3 agora: {top3}"


def test_lists_report_bytes_per_item(report):
    lists = [r for r in report if r["items"] > 1 and r["tool"] == "query_items"]
    assert lists, "nenhuma listagem medida"
    assert all(r["bytes_per_item"] for r in lists)
