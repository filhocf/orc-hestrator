"""RED (RFC-003 / FEAT-0) — eliminação do payload duplicado `structuredContent`.

Defeito medido: as 31 tools retornam `-> str` e devolvem `json.dumps(...)`. O
FastMCP (mcp 1.27.0) trata `-> str` como anotação serializável e cria um
output model `{'result': str}` — então cada resposta MCP carrega o texto NOVE
VEZES NO DOIS: um `TextContent` com a string E `structuredContent={'result':
<mesma string>}`. Medição de referência: 5 itens × ~500 bytes => TextContent
2.500 b + structuredContent 2.594 b = 5.094 b (com `structured_output=False`
=> 2.500 b, −51%).

Este teste trava a correção por DOIS ângulos, ambos verificáveis no estado
RED (falham hoje) e GREEN (passam com `@mcp.tool(structured_output=False)`):

- `test_no_tool_exposes_output_schema` — nenhuma tool expõe `outputSchema` no
  `list_tools` (o contrato que faz o low-level server serializar
  `structuredContent` na resposta da wire).
- `test_call_tool_returns_only_text` — `mcp.call_tool` (superfície REAL
  in-process) devolve APENAS os `ContentBlock`s de texto: sem a tupla
  `(content, structured_content)` que leva o dicionário duplicado. Para cada
  uma das 31 tools, chamamos com argumentos mínimos válidos e assertamos o
  shape do retorno.

Superfície REAL: `from task_orchestrator.server import mcp` +
`mcp.call_tool` / `mcp.list_tools` (o banco é redirecionado para SQLite
temporário pelo fixture autouse `engine_db` do conftest). Os argumentos são
mínimos (todos os parâmetros obrigatórios são `str`); as tools capturam
exceções e devolvem JSON de erro, então o estado do banco irrelevante.

NÃO altere os testes existentes (`test_onboarding.py` etc.) para fazer este
passar: eles leem o texto normalizado e devem seguir verdes.
"""

import asyncio
import json

from task_orchestrator.server import mcp

# Argumetos mínimos para cada tool (todos os params obrigatórios são str).
# Tools com parâmetros com default recebem {} — o argumento é apenas um
# carrier para exercitar o shape de retorno, não o domínio.
MINIMAL_ARGS: dict[str, dict[str, str]] = {
    "advance_item": {},
    "agent_end": {"session_id": "test-session"},
    "agent_heartbeat": {"session_id": "test-session"},
    "agent_list": {},
    "agent_register": {},
    "claim": {
        "subject_type": "work_item",
        "subject_ref": "nonexistent-item",
        "session_id": "test-session",
    },
    "complete_tree": {"parent_id": "nonexistent-item"},
    "conflicts": {"subjects_json": "[]", "session_id": "test-session"},
    "create_work_tree": {"root_title": "RED probe"},
    "export_graph": {},
    "get_blocked_items": {},
    "get_context": {},
    "get_execution_stack": {},
    "get_metrics": {},
    "get_next_item": {},
    "get_next_status": {"item_id": "nonexistent-item", "trigger": "start"},
    "get_project_graph_metrics": {},
    "get_workspace_context": {"workspace_name": "nonexistent-workspace"},
    "import_graph": {"data_json": "{}"},
    "manage_archive": {"operation": "stats"},
    "manage_checkpoints": {"operation": "list"},
    "manage_dependencies": {"operation": "query", "item_id": "nonexistent-item"},
    "manage_items": {"operation": "list"},
    "manage_notes": {"operation": "list", "item_id": "nonexistent-item"},
    "manage_schemas": {"operation": "list"},
    "manage_workspaces": {"operation": "list"},
    "orc_onboarding": {"client_type": "hermes"},
    "query_dependencies": {"item_id": "nonexistent-item"},
    "query_items": {"operation": "list"},
    "query_notes": {"item_id": "nonexistent-item"},
    "release": {
        "subject_type": "work_item",
        "subject_ref": "nonexistent-item",
        "session_id": "test-session",
    },
}


def _tool_names() -> set[str]:
    return set(MINIMAL_ARGS)


def test_tool_registry_covers_all_31_tools() -> None:
    """Guarda contra drift: o inventário MINIMAL_ARGS == as 31 tools reais."""
    names = [t.name for t in asyncio.run(mcp.list_tools())]
    assert _tool_names() == set(names), (
        f"drift no inventário: no registro {sorted(set(names) - _tool_names())} "
        f"sobrando no inventário {sorted(_tool_names() - set(names))}"
    )
    assert len(names) == 31


def test_no_tool_exposes_output_schema() -> None:
    """Nenhuma tool pode expor outputSchema (o que dispara structuredContent)."""
    tools = asyncio.run(mcp.list_tools())
    offenders = [t.name for t in tools if t.outputSchema is not None]
    assert not offenders, (
        "tools expondo outputSchema (duplo payload na resposta MCP): "
        + ", ".join(sorted(offenders))
    )


def test_call_tool_returns_only_text() -> None:
    """`mcp.call_tool` devolve apenas ContentBlocks de texto, sem o dicionário
    estruturado duplicado.

    RED: com `-> str` e output model derivado, o retorno é a tupla
    `(content, {'result': '<mesma string>'})` — o segundo elemento É o
    `structuredContent` que a wire envia. GREEN: com
    `structured_output=False`, o retorno é só a lista de TextContent.
    """
    # `get_next_status` resolve o id sem try/except (raise vira ToolError),
    # então usa um item REAL criado no banco temporário do conftest.
    created = asyncio.run(
        mcp.call_tool("manage_items", {"operation": "create", "title": "RED probe"})
    )
    created_blocks = created[0] if isinstance(created, tuple) else created
    item = json.loads(created_blocks[0].text)
    assert not item.get("error"), f"create para o probe falhou: {item}"
    item_id = item.get("id") or item.get("item_id")
    args = {name: dict(a) for name, a in MINIMAL_ARGS.items()}
    args["get_next_status"]["item_id"] = item_id

    failures: list[str] = []
    for name, a in sorted(args.items()):
        result = asyncio.run(mcp.call_tool(name, a))
        if isinstance(result, tuple):
            structured = result[1]
            dup = (
                json.dumps(structured, ensure_ascii=False)
                if structured is not None
                else "<none>"
            )
            failures.append(f"{name}: retornou tupla com structuredContent {dup[:80]}")
            continue
        blocks = result if isinstance(result, list) else [result]
        texts = [b for b in blocks if getattr(b, "type", None) == "text"]
        assert texts, f"{name}: nenhum ContentBlock de texto no retorno {result!r}"
    assert not failures, "structuredContent ainda presente em:\n" + "\n".join(failures)
