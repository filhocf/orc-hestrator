# Client connection recipes

The server teaches itself through `orc_onboarding(client_type, lang)`
(client_type ∈ hermes/kiro/cli/claude; unknown → generic). These are the
connection essentials per client.

## Transport

- `orc` and `orc-mcp` run **stdio** (in the client's process).
- `orc-serve` runs **streamable-http** (a central server), and needs the `ui`
  extra: `uvx --from 'orc-hestrator-server[ui]' orc-serve`. Without `fastapi`
  the process dies with `ModuleNotFoundError: fastapi`.
- `MCP_TRANSPORT` overrides; `MCP_HOST`/`MCP_PORT` set the bind (default
  `127.0.0.1:3201`; a reference deployment uses `8005` behind a proxy).

## Kiro

Point the MCP config at the server URL (`https://host/orc/mcp`) with auth
headers. Identity via the `X-Agent-ID` header or the `MCP_AGENT_ID` env var.

```json
{
  "mcpServers": {
    "orc": {
      "url": "https://host/orc/mcp",
      "headers": { "X-Agent-ID": "your-agent-name" }
    }
  }
}
```

## Claude (Desktop / Code)

Add the server to `claude_desktop_config.json` or the Claude Code `.mcp.json`,
pointing at the Orc URL with the proxy's auth headers. Identity via `X-Agent-ID`
or `MCP_AGENT_ID`. First call: `orc_onboarding`, then
`get_context(verbosity="compact")`.

## Hermes

Identity through `identity_header` (`name: X-Agent-ID`, `value_from: profile`) —
your `agent_id` becomes the Hermes profile name. Auth by header: Bearer when the
server's OAuth2 is on, Basic at the reverse-proxy edge. The tool cut is
client-side config (the server does not filter tools): a nucleo set for the main
agent, a read-only set for subagents, a full set for operations.

## CLI / local

```bash
MCP_AGENT_ID=your-name uv run orc            # stdio
MCP_AGENT_ID=your-name orc-serve             # streamable-http (needs [ui])
```

## First call, any client

```
orc_onboarding(client_type="<yours>")   # the server explains itself
get_context(verbosity="compact")         # cheap board snapshot
```
