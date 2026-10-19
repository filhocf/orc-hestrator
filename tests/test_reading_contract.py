"""Caracterização do contrato de leitura do Orc (RFC-003, invariante 2).

Por que este teste existe: as fatias de economia de contexto (FEAT-1, FEAT-2,
FEAT-6b) mudam o que o servidor DEVOLVE. Economizar token é mudar contrato de
leitura, e sem uma régua pareada a regressão é silenciosa — o payload encolhe
onde ninguém pediu, ou cresce de volta no próximo default.

O que fica fixado: o payload das chamadas de rotina da régua
(`scripts/measure_payload.py`), medido sobre a mesma placa determinística de 64
itens. Se uma feature muda a saída SEM o parâmetro ligado, este teste falha.

Normalização: a placa é recriada a cada execução, então UUIDs, timestamps,
`lead_time_avg_seconds` e `week` mudam por construção. O script normaliza esses
valores (ver `normalize_payload` lá) e o `chars` daqui é o do payload
NORMALIZADO. O tamanho real em bytes continua sendo o da tabela/`--json` da
régua, que não normaliza — é esse número que o RFC cita, e bytes/4 é a
conversão usada no RFC para estimar tokens.

Como regravar o baseline (só quando a mudança de payload for INTENCIONAL e
aprovada no gate da feature que a causou):

    ORC_UPDATE_BASELINE=1 uv run pytest tests/test_reading_contract.py -q

Sem essa variável o teste nunca escreve no disco.

Sobre o tempo: a placa é construída RELATIVA a `now` (itens velhos nascem com
`now - 30 dias`, `due_at` como `now - 30 + n`), então `stale_days`, `overdue` e
`due_soon` não envelhecem entre execuções nem viram flake na virada do dia. O
que muda com o calendário — a semana ISO de `get_metrics` — está normalizado.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "measure_payload.py"
DATA = Path(__file__).resolve().parent / "data"
BASELINE_JSON = DATA / "reading_contract_baseline.json"
BASELINE_TEXTS = DATA / "reading_contract"

# As 6 chamadas de rotina do RFC, mais as duas de notas e as duas variações de
# lista que a régua mede. O superset é proposital: o que a sessão paga inclui
# todas elas, não só as seis citadas na tabela do RFC.
EXPECTED_KEYS = {
    "01-get_context",
    "02-query_items",
    "03-query_items",
    "04-query_items",
    "05-get_blocked_items",
    "06-get_next_item",
    "07-get_execution_stack",
    "08-get_metrics",
    "09-query_notes",
    "10-query_notes",
}
ROUTINE_TOOLS = {
    "get_context",
    "query_items",
    "get_blocked_items",
    "get_next_item",
    "get_execution_stack",
    "get_metrics",
}


def _first_difference(expected: str, actual: str) -> str:
    """Onde os dois payloads divergem — o offset vale mais que 'diferente'."""
    limit = min(len(expected), len(actual))
    for i in range(limit):
        if expected[i] != actual[i]:
            lo = max(0, i - 60)
            return (
                f"primeira diferença no offset {i} "
                f"(esperado {len(expected)} chars, medido {len(actual)})\n"
                f"  esperado: ...{expected[lo : i + 60]!r}\n"
                f"  medido:   ...{actual[lo : i + 60]!r}"
            )
    if len(expected) != len(actual):
        longer = "medido" if len(actual) > len(expected) else "esperado"
        tail = (actual if longer == "medido" else expected)[limit:]
        return (
            f"prefixo idêntico; {longer} tem {len(tail)} chars a mais no fim: "
            f"{tail[:120]!r}"
        )
    return "sem diferença (o chamador não deveria ter pedido o diff)"


@pytest.fixture(scope="module")
def measured(tmp_path_factory) -> list[dict]:
    """Roda a régua uma vez e devolve os digests normalizados."""
    out = tmp_path_factory.mktemp("reading-contract")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--digest", "--dump", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, f"régua falhou:\n{proc.stderr[-2000:]}"
    digests = json.loads(proc.stdout)
    for entry in digests:
        entry["text"] = (out / f"{entry['key']}.txt").read_text("utf-8")
    return digests


def test_the_ruler_covers_every_routine_call(measured):
    keys = {entry["key"] for entry in measured}
    assert keys == EXPECTED_KEYS, (
        f"régua mudou de escopo: {sorted(keys ^ EXPECTED_KEYS)}"
    )
    assert ROUTINE_TOOLS <= {entry["tool"] for entry in measured}


def test_measurement_is_internally_consistent(measured):
    """chars e sha256 do relatório têm de descrever o texto efetivamente gravado."""
    for entry in measured:
        text = entry["text"]
        assert entry["chars"] == len(text), f"{entry['key']}: chars não fecha"
        assert entry["sha256"] == hashlib.sha256(text.encode()).hexdigest(), (
            f"{entry['key']}: sha não descreve o texto medido"
        )
        assert entry["est_tokens"] == round(len(text) / 4)


def test_payload_contract_matches_baseline(measured):
    """O contrato de leitura de hoje é byte-idêntico ao baseline aprovado."""
    if os.environ.get("ORC_UPDATE_BASELINE") == "1":
        # Guarda: variável herdada em pipeline branquearia uma regressão real e
        # o teste passaria (skip) exatamente quando deveria falhar.
        assert not (os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")), (
            "ORC_UPDATE_BASELINE=1 sob CI: regravar o baseline em pipeline "
            "apaga a evidência de regressão de contrato"
        )
        BASELINE_TEXTS.mkdir(parents=True, exist_ok=True)
        DATA.mkdir(parents=True, exist_ok=True)
        for entry in measured:
            (BASELINE_TEXTS / f"{entry['key']}.txt").write_text(entry["text"], "utf-8")
        BASELINE_JSON.write_text(
            json.dumps(
                [{k: v for k, v in entry.items() if k != "text"} for entry in measured],
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            "utf-8",
        )
        pytest.skip("baseline regravado sob ORC_UPDATE_BASELINE=1")

    if not BASELINE_JSON.exists():
        pytest.skip(
            f"baseline ausente ({BASELINE_JSON}); gere com "
            "ORC_UPDATE_BASELINE=1 e revise o diff antes de commitar"
        )
    baseline = {
        entry["key"]: entry for entry in json.loads(BASELINE_JSON.read_text("utf-8"))
    }

    problems = []
    for entry in measured:
        key = entry["key"]
        expected_entry = baseline.get(key)
        assert expected_entry is not None, f"{key}: chamada nova sem baseline"
        expected_file = BASELINE_TEXTS / f"{key}.txt"
        assert expected_file.exists(), f"{key}: baseline de texto ausente"
        expected = expected_file.read_text("utf-8")
        if expected != entry["text"]:
            problems.append(
                f"{key} ({entry['tool']}): {_first_difference(expected, entry['text'])}"
            )
    assert not problems, "contrato de leitura mudou:\n\n" + "\n\n".join(problems)


def test_baseline_records_the_numbers_the_rfc_quotes(measured):
    """O baseline carrega os chars que sustentam os ACs do RFC-003.

    Não fixa valor absoluto (o board muda), mas exige que o número esteja
    presente e coerente para cada chamada — sem isso o AC vira opinião.
    """
    if not BASELINE_JSON.exists():
        pytest.skip("baseline ausente")
    baseline = json.loads(BASELINE_JSON.read_text("utf-8"))
    for entry in baseline:
        assert entry["chars"] > 0, f"{entry['key']}: baseline sem medição"
        assert entry["est_tokens"] == round(entry["chars"] / 4)
