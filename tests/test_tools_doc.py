"""RED tests (G3) — fatia F7: ``docs/TOOLS.md`` gerado a partir do servidor (R5).

Contrato do gerador (novo): ``scripts/generate_tools_doc.py``:
- sem flag, escreve ``docs/TOOLS.md`` a partir de ``tools/list`` +
  ``prompts/list`` + ``resources/list`` do servidor;
- ``--check`` compara o arquivo em disco com o que o servidor registra e sai
  com código DIFERENTE de zero se divergir.

Os números reais do servidor (medidos no G0): **31 tools, 7 prompts,
6 resources** (3 base + 3 ``/pt-br``). O ``TOOLS.md`` atual MENTE: declara
``3 resources``. Os dois testes falham hoje porque o script ainda não existe
(e o arquivo em disco ainda diz 3 resources):

- ``test_check_passes_when_doc_matches`` — ``--check`` sai 0 e o arquivo
  declara as contagens reais (31/7/6).
- ``test_check_fails_when_doc_tampered`` — adulterar o arquivo à mão faz o
  ``--check`` falhar (código != 0).
"""

import re
import shutil
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_TOOLS_DOC = _REPO / "docs" / "TOOLS.md"
_GENERATOR = _REPO / "scripts" / "generate_tools_doc.py"


def _run_check() -> int:
    """Roda ``uv run python scripts/generate_tools_doc.py --check`` e devolve o
    código de saída."""
    proc = subprocess.run(
        ["uv", "run", "python", str(_GENERATOR), "--check"],
        cwd=_REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode


def test_check_passes_when_doc_matches():
    """R5/AC5: ``--check`` passa (exit 0) quando o doc bate com o servidor, e o
    arquivo declara as contagens REAIS (31 tools, 7 prompts, 6 resources).

    Comportamento travado: com o ``docs/TOOLS.md`` gerado a partir do servidor
    (contagem e nomes NUNCA digitados à mão), ``generate_tools_doc.py --check``
    compara e sai 0. E o arquivo deve trazer as contagens reais medidas no
    servidor — 31 tools, 7 prompts e 6 resources (hoje o arquivo diz 3). Hoje o
    script não existe (exit != 0) e o arquivo mente (3 resources) — falha.
    """
    code = _run_check()
    assert code == 0, (
        f"generate_tools_doc.py --check saiu {code} (esperado 0): o doc não "
        "bate com o servidor ou o script não existe (R5)"
    )

    doc = _TOOLS_DOC.read_text(encoding="utf-8")
    assert re.search(r"Tools:\s*\*{0,2}\s*31\b", doc), (
        "TOOLS.md deve declarar 31 tools (R5: contagem vinda de tools/list)"
    )
    assert re.search(r"Prompts:\s*\*{0,2}\s*7\b", doc), (
        "TOOLS.md deve declarar 7 prompts (R5: contagem vinda de prompts/list)"
    )
    assert re.search(r"Resources:\s*\*{0,2}\s*6\b", doc), (
        "TOOLS.md deve declarar 6 resources (R5: 3 base + 3 /pt-br); "
        "o arquivo atual mente com 3"
    )


def test_check_fails_when_doc_tampered():
    """R5/AC5: adulterar ``docs/TOOLS.md`` à mão faz o ``--check`` falhar.

    Comportamento travado: cópia o doc para backup, injeta uma linha
    adulterada ao final, roda ``generate_tools_doc.py --check`` e asserta o
    código de saída DIFERENTE de zero (o arquivo diverge do servidor). O
    arquivo original é restaurado no ``finally``. Hoje o script não existe — o
    ``--check`` sai != 0, mas o teste continua valendo como trava de contrato
    para o G4 (com o script presente, adulterar o doc deve fazê-lo falhar).
    """
    backup = _REPO / "docs" / "TOOLS.md.g3_backup"
    # Pré-condição honesta: para provar que o --check DETECTA adulteração, o
    # gerador precisa existir (sem ele, `--check` sai != 0 por "arquivo não
    # encontrado", não por divergência — passaria de forma vacua).
    assert _GENERATOR.exists(), (
        "generator scripts/generate_tools_doc.py não existe — não dá para "
        "verificar o modo --check de detecção de adulteração (R5/AC5)"
    )
    shutil.copy2(_TOOLS_DOC, backup)
    try:
        tampered = "## TAMPERED-LINE-G3-DO-NOT-EDIT\n"
        with _TOOLS_DOC.open("a", encoding="utf-8") as f:
            f.write(tampered)

        code = _run_check()
        assert code != 0, (
            "generate_tools_doc.py --check saiu 0 após adulterar o doc: "
            "o modo --check não detectou a divergência (R5/AC5)"
        )
    finally:
        # restaura o arquivo original, com ou sem falha
        shutil.move(str(backup), str(_TOOLS_DOC))
