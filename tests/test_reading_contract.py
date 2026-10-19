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


# Sinais de pipeline conhecidos. GitHub Actions seta CI, mas Jenkins só
# JENKINS_URL, GitLab só GITLAB_CI, e assim por diante: guardar apenas contra CI
# deixaria os outros regravarem o baseline e assentarem a regressão.
CI_ENV_VARS = (
    "CI",
    "GITHUB_ACTIONS",
    "JENKINS_URL",
    "GITLAB_CI",
    "CIRCLECI",
    "TRAVIS",
    "BUILDKITE",
    "TF_BUILD",
    "TEAMCITY_VERSION",
    "BITBUCKET_BUILD_NUMBER",
)


def _running_in_ci() -> bool:
    return any(os.environ.get(name) for name in CI_ENV_VARS)


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
    longer = "medido" if len(actual) > len(expected) else "esperado"
    tail = (actual if longer == "medido" else expected)[limit:]
    return (
        f"prefixo idêntico; {longer} tem {len(tail)} chars a mais no fim: "
        f"{tail[:120]!r}"
    )


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
        assert not _running_in_ci(), (
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

    # O baseline é versionado: ausência não é motivo para pular a garantia, é
    # instalação quebrada. Skip aqui deixaria um fork/clone verde sem contrato.
    assert BASELINE_JSON.exists(), (
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
        assert entry["args"] == expected_entry["args"], (
            f"{key}: argumentos da chamada mudaram "
            f"(esperado {expected_entry['args']}, medido {entry['args']})"
        )
        expected_file = BASELINE_TEXTS / f"{key}.txt"
        assert expected_file.exists(), f"{key}: baseline de texto ausente"
        expected = expected_file.read_text("utf-8")
        if expected != entry["text"]:
            problems.append(
                f"{key} ({entry['tool']}): {_first_difference(expected, entry['text'])}"
            )
    assert not problems, "contrato de leitura mudou:\n\n" + "\n\n".join(problems)


NORMALIZATION_CASES = [
    # (payload, esperado conter, esperado NÃO conter, o que a garantia protege)
    (
        '{"lead_time_avg_seconds": 0.0008443750000000001}',
        "<number>",
        "0.000844",
        "float volátil",
    ),
    (
        '{"lead_time_avg_seconds": "1.2h"}',
        "1.2h",
        "<number>",
        "mudança de tipo sob a chave",
    ),
    ('{"lead_time_avg_seconds": 3}', "<number>", "3", "int também é medição"),
    ('{"week": "2026-W43"}', "<week>", "2026-W43", "semana ISO volátil"),
    ('{"week": "2026-10"}', "2026-10", "<week>", "perda de granularidade semanal"),
    (
        '{"id": "305aeaad-e0d6-4cb9-b84a-9cab514ea915"}',
        "<uuid>",
        "305aeaad",
        "uuid volátil",
    ),
    ('{"id": "305aeaad"}', "305aeaad", "<uuid>", "uuid truncado"),
    (
        '{"at": "2026-10-19T18:08:00.123456+00:00"}',
        "<timestamp>",
        "18:08",
        "timestamp volátil",
    ),
    (
        '{"at": "2026-10-19 18:08:00Z"}',
        "<timestamp>",
        "18:08",
        "timestamp sem microssegundos",
    ),
    (
        '{"n": 8, "title": "ARC-0: arco de teste"}',
        "ARC-0",
        "<number>",
        "contrato intacto",
    ),
]


@pytest.fixture(scope="module")
def normalized_batch() -> dict[str, str]:
    """Normaliza todos os casos numa única chamada de processo."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--normalize"],
        cwd=REPO,
        input=json.dumps([payload for payload, *_ in NORMALIZATION_CASES]),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-1000:]
    return dict(
        zip(
            (case[0] for case in NORMALIZATION_CASES),
            json.loads(proc.stdout),
            strict=True,
        )
    )


@pytest.mark.parametrize(
    ("payload", "must_contain", "must_not_contain", "razao"),
    NORMALIZATION_CASES,
)
def test_normalization_is_value_based_not_key_based(
    normalized_batch, payload, must_contain, must_not_contain, razao
):
    """Achado do G5: normalizar por NOME de chave mascararia mudança de contrato.

    Se `lead_time_avg_seconds` deixasse de ser float (segundos) e virasse string
    legível, ou se `week` passasse a ser agregado mensal, um normalizador
    key-based daria PASS — regressão silenciosa. Aqui se prova que a troca de
    tipo/formato APARECE e que só o valor volátil é substituído.
    """
    out = normalized_batch[payload]
    assert must_contain in out, f"{razao}: esperava {must_contain!r} em {out!r}"
    assert must_not_contain not in out, (
        f"{razao}: {must_not_contain!r} foi normalizado fora — a mudança sumiria"
    )


def test_normalization_falls_back_for_non_json():
    """Payload não-JSON ainda normaliza semana e timestamp (mesma garantia)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--normalize"],
        cwd=REPO,
        input="semana 2026-W43 em 2026-10-19T18:08:00+00:00",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-1000:]
    assert "2026-W43" not in proc.stdout
    assert "18:08" not in proc.stdout


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
