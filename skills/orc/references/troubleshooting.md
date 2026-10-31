# Troubleshooting

## 401 at the proxy

`GET https://host/orc/` or `/orc/mcp` returns 401 (realm e.g. "Orc Hub") when the
reverse proxy's basic auth is missing or wrong. `/orc/health` answers 200 without
auth — use it to tell "server down" from "auth wrong". Fix: supply the proxy
credentials in your client's headers. A wrong credential breaks every client
pointed at that URL, not just yours.

## `ModuleNotFoundError: fastapi`

`orc-serve` (streamable-http) needs the `ui` extra. A plain `uv sync` or
`uv run` can rebuild the venv without `fastapi` and the process dies on boot.
Fix: `uv sync --extra ui` (dev) or `uvx --from 'orc-hestrator-server[ui]'
orc-serve` (run). stdio (`orc`, `orc-mcp`) does not need it.

## `initialize` reports the SDK version, not the product

If `serverInfo.version` looks like the MCP SDK version, you are reading the wrong
field or an old build. The product version comes from the package metadata and is
also on `/health`. Not actionable from the client side beyond upgrading.

## Writes recorded with a null author

Your `X-Agent-ID` is not reaching the server. Identity resolves per request from
argument → `X-Agent-ID` header → `MCP_AGENT_ID` env → OAuth client id. Set one of
them. URL-embedded userinfo (`https://user:pass@host/...`) is not treated as
identity by every transport — prefer an explicit header.

## My session's claims vanished

Sessions idle for more than 300 seconds are reaped, which releases their claims.
Send `agent_heartbeat(session_id)` every 2-3 minutes while you hold work.

## `create_work_tree` rejects my payload

It requires `root_title` (not `root: {...}`), `children_json` as a JSON array of
`{ref, title, ...}`, and `deps_json` using the `ref` names. A structured error
names the offending field — read `error.field`.

## A transition is refused

Run `get_next_status(item_id, trigger)` to see the blockers, and
`manage_schemas(check, item_id=...)` to see which required note is missing. Either
a dependency has not reached its `unblock_at`, or a note gate is unsatisfied.

## stdio vs streamable-http

stdio runs inside the client process (one agent, local). streamable-http is the
central server many agents and machines share. If you expect shared state and see
only your own items, you are probably on stdio against a local database — point at
the server URL instead.
