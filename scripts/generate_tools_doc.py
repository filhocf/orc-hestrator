"""Generate docs/TOOLS.md from the MCP server (F7 R5).

Reads ``tools/list``, ``prompts/list`` and ``resources/list`` from the running
server object and rewrites ``docs/TOOLS.md`` so that counts and names are never
typed by hand. Prompts are only registered inside ``main()``, so this script
calls ``register_prompts(mcp)`` itself.

Usage:
    uv run python scripts/generate_tools_doc.py          # write docs/TOOLS.md
    uv run python scripts/generate_tools_doc.py --check  # exit != 0 if the doc diverges
"""

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS_DOC = REPO / "docs" / "TOOLS.md"


def _render(tools, prompts, resources) -> str:
    lines = [
        "# Tools reference",
        "",
        "Generated from tools/list. Do not edit by hand: counts and names come",
        "from the server (`tools/list`, `prompts/list`, `resources/list`).",
        "",
        (
            f"Tools: **{len(tools)}** · Prompts: **{len(prompts)}** · "
            f"Resources: **{len(resources)}**"
        ),
        "",
        "## Tools",
        "",
        "| Tool | Description |",
        "|---|---|",
    ]
    for t in tools:
        lines.append(f"| `{t.name}` | {t.description or ''} |")
    lines += [
        "",
        "## Prompts",
        "",
        "| Prompt | Description |",
        "|---|---|",
    ]
    for p in prompts:
        lines.append(f"| `{p.name}` | {p.description or ''} |")
    lines += [
        "",
        "## Resources",
        "",
        "| URI | Description |",
        "|---|---|",
    ]
    for r in resources:
        lines.append(f"| `{r.uri}` | {r.description or ''} |")
    lines.append("")
    return "\n".join(lines)


def _collect() -> str:
    from task_orchestrator.prompts import register_prompts
    from task_orchestrator.server import mcp

    async def _lists():
        register_prompts(mcp)  # only registered inside main() otherwise
        tools = await mcp.list_tools()
        prompts = await mcp.list_prompts()
        resources = await mcp.list_resources()
        return tools, prompts, resources

    tools, prompts, resources = asyncio.run(_lists())
    return _render(tools, prompts, resources)


def main() -> int:
    expected = _collect()
    if "--check" in sys.argv[1:]:
        if not TOOLS_DOC.exists():
            print(
                f"error: {TOOLS_DOC} not found (run without --check to generate)",
                file=sys.stderr,
            )
            return 1
        on_disk = TOOLS_DOC.read_text(encoding="utf-8")
        if on_disk != expected:
            print(
                "error: docs/TOOLS.md diverges from the server; regenerate it:",
                file=sys.stderr,
            )
            print("    uv run python scripts/generate_tools_doc.py", file=sys.stderr)
            return 1
        print(f"ok: {TOOLS_DOC} matches the server")
        return 0
    TOOLS_DOC.write_text(expected, encoding="utf-8")
    print(f"wrote {TOOLS_DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
