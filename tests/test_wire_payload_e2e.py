"""E2E do contrato de payload (RFC-003 / FEAT-0) — sobre a wire, não in-process.

Sobe o entry point `orc` de verdade (transporte stdio, JSON-RPC), inicializa a
sessão MCP e chama tools reais. O que se prova aqui não pode ser provado por
`mcp.call_tool` in-process: é o servidor de verdade serializando a resposta.

Duas asserções, ambas sobre a resposta do protocolo:

1. `tools/list` não anuncia `outputSchema` em nenhuma tool.
2. `tools/call` devolve conteúdo de texto e **nenhum** `structuredContent`.

Sem o `structured_output=False` (o estado anterior), cada resposta carregava o
mesmo payload duas vezes: um `TextContent` com a string JSON e
`structuredContent={'result': <a mesma string>}`.

Este teste gasta um subprocesso por sessão; mantenha-o enxuto.
"""

import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


def _text(content) -> str:
    """Primeiro bloco de texto da resposta (o protocolo permite outros tipos)."""
    parts = [c.text for c in content if isinstance(c, TextContent)]
    assert parts, f"resposta sem TextContent: {[type(c).__name__ for c in content]}"
    return parts[0]


REPO = Path(__file__).resolve().parents[1]
ORC_BIN = REPO / ".venv" / "bin" / "orc"


@pytest.fixture()
def orc_stdio(tmp_path, monkeypatch):
    """Sobe `orc` em stdio contra um banco temporário e devolve os params."""
    db_file = tmp_path / "wire.db"
    env = dict(os.environ)
    env["ORC_DB"] = str(db_file)
    env.pop("MCP_TRANSPORT", None)  # o entry point decide; force o default (stdio)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "task_orchestrator.server"],
        env=env,
        cwd=str(REPO),
    )
    return params


@pytest.mark.anyio
async def test_wire_payload_has_no_structured_content(orc_stdio):
    async with (
        stdio_client(orc_stdio) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        # 1. Nenhuma tool anuncia outputSchema (é o que faz o server
        #    serializar structuredContent na resposta).
        listing = await session.list_tools()
        with_schema = [
            t.name for t in listing.tools if getattr(t, "outputSchema", None)
        ]
        assert with_schema == [], f"tools com outputSchema: {with_schema}"
        assert len(listing.tools) == 31, f"esperava 31 tools, veio {len(listing.tools)}"

        # 2. Uma escrita e uma leitura reais, medidas na wire.
        created = await session.call_tool(
            "manage_items",
            {"operation": "create", "title": "wire payload", "description": "x" * 400},
        )
        assert created.structuredContent is None, (
            "escrita ainda devolveu structuredContent"
        )
        item = json.loads(_text(created.content))
        assert item["title"] == "wire payload"

        listed = await session.call_tool(
            "query_items", {"operation": "list", "limit": 10}
        )
        assert listed.structuredContent is None, (
            "leitura ainda devolveu structuredContent"
        )

        text = _text(listed.content)
        payload = json.loads(text)
        assert isinstance(payload, list) and payload
        # O payload é texto puro: nada de envelope duplicado.
        assert len(text.encode()) > 400, "payload suspeitosamente pequeno"
