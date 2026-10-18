"""RED tests (G5.1) — fatia F7: texto de onboarding ensina os comandos reais (R8).

O texto de onboarding (F1) DEVE ensinar os comandos que existem:
``uv run orc`` (stdio) e ``orc-serve`` (streamable-http) — e NUNCA o nome
antigo ``task-orchestrator-py``. O nome da DISTRIBUIÇÃO
(``orc-hestrator-server``) NÃO é um comando e não deve ser ensinado como
tal: ``uv run orc-hestrator-server`` falha com "Failed to spawn" (P1-1 do
G5). Um teste in-process sobre ``task_orchestrator.onboarding`` cobre a
variante ``cli`` nos dois idiomas (``en`` e ``pt-BR``).

Contrato travado (R8 corrigido no G5): para ``client_type="cli"``, em
``en`` e em ``pt-BR``, o texto contém ``uv run orc`` (stdio) e
``orc-serve`` (streamable-http) e NÃO contém ``uv run orc-hestrator-server``
nem ``task-orchestrator-py``. Hoje a variante ``cli`` ainda ensina
``uv run orc-hestrator-server`` — falha.
"""

import re

from task_orchestrator.onboarding import build_onboarding_text
from task_orchestrator.server import mcp

_LANGS = ("en", "pt-BR")


def test_cli_onboarding_teaches_new_commands():
    """R8/G5 (P1-1): a variante ``cli`` (en e pt-BR) ensina os comandos reais.

    Comportamento travado: para ``client_type="cli"``, em ``en`` e ``pt-BR``,
    o texto servido contém ``uv run orc`` (stdio) e ``orc-serve``
    (comando de deploy/streamable-http, ADR-007) e NÃO contém
    ``uv run orc-hestrator-server`` — o nome da DISTRIBUIÇÃO não é comando,
    e ``uv run <nome>`` só funciona para console scripts (R8 corrigido no
    G5) — nem o nome antigo ``task-orchestrator-py`` (AC7). A busca do
    comando stdio usa o look-ahead ``(?!-)`` para não casar ``orc`` como
    prefixo de outro script (ex.: ``orc-hestrator-server``). Hoje a variante
    ainda ensina ``uv run orc-hestrator-server`` — falha.
    """
    for lang in _LANGS:
        text = build_onboarding_text("cli", lang, mcp)
        low = text.lower()

        assert re.search(r"uv run orc(?!-)", low), (
            f"variante cli (lang={lang!r}) deve ensinar 'uv run orc' (stdio, "
            "R8/R2.1: quick-start publicado)"
        )
        assert "orc-serve" in low, (
            f"variante cli (lang={lang!r}) deve ensinar 'orc-serve' "
            "(R8/ADR-007: comando de deploy streamable-http)"
        )
        assert "uv run orc-hestrator-server" not in low, (
            f"variante cli (lang={lang!r}) NÃO deve ensinar "
            "'uv run orc-hestrator-server': o nome da distribuição não é "
            "comando (R8 corrigido no G5, P1-1)"
        )
        assert "task-orchestrator-py" not in low, (
            f"variante cli (lang={lang!r}) NÃO deve mais mencionar o nome "
            "antigo 'task-orchestrator-py' (R8/AC7)"
        )
