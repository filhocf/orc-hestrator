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


def _normalize_description(text: str) -> str:
    """Normalize server-provided text so the doc is byte-identical per interpreter.

    CPython >= 3.13 automatically applies a cleandoc-like cleanup to function
    docstrings; 3.11/3.12 keep the raw indentation. The MCP SDK exposes
    ``fn.__doc__`` verbatim as tool/prompt/resource descriptions, so the
    rendered text differs per Python version. This applies the same cleanup
    explicitly — cleandoc semantics (lstrip the first line, strip the common
    margin of continuation lines, expand tabs) but without stripping leading
    or trailing blank lines, matching the 3.13+ behavior byte-for-byte.
    """
    if not text:
        return text
    try:
        lines = text.expandtabs().split("\n")
    except UnicodeError:
        return text
    lines[0] = lines[0].lstrip()
    margin = sys.maxsize
    for line in lines[1:]:
        content = len(line.lstrip())
        if content:
            margin = min(margin, len(line) - content)
    if margin < sys.maxsize:
        for i in range(1, len(lines)):
            lines[i] = lines[i][margin:]
    return "\n".join(lines)


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
        lines.append(f"| `{t.name}` | {_normalize_description(t.description or '')} |")
    lines += [
        "",
        "## Prompts",
        "",
        "| Prompt | Description |",
        "|---|---|",
    ]
    for p in prompts:
        lines.append(f"| `{p.name}` | {_normalize_description(p.description or '')} |")
    lines += [
        "",
        "## Resources",
        "",
        "| URI | Description |",
        "|---|---|",
    ]
    for r in resources:
        lines.append(f"| `{r.uri}` | {_normalize_description(r.description or '')} |")
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
