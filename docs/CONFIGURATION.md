# Configuration

## Commands

The transport is chosen by the entry point (ADR-007), not by an environment
variable:

| Command | Transport | Purpose |
|---|---|---|
| `orc` | stdio | MCP server inside the client's process |
| `orc-mcp` | stdio | Explicit stdio alias |
| `orc-serve` | streamable-http | Central HTTP server on `MCP_HOST`/`MCP_PORT` |
| `orc-ui` | HTTP (own port) | Lightweight server-rendered board |
| `orc-hestrator` | stdio | Distribution-homonym script (what `uvx orc-hestrator-server` runs) |

`MCP_TRANSPORT` remains as an override for tests and edge cases. The legacy
scripts `task-orchestrator-py` / `task-orchestrator-ui` still work and print a
deprecation warning on stderr.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ORC_DB` | `~/.orc/tasks.db` | SQLite database path |
| `ORC_CONFIG` | `.taskorchestrator/config.yaml` | Note-schema configuration file |
| `ORC_LANG` | `en` | Language for the onboarding surface: `en` or `pt-BR` |
| `MCP_TRANSPORT` | by entry point | Override only — `orc`/`orc-mcp` run stdio, `orc-serve` runs streamable-http (ADR-007) |
| `MCP_HOST` | `127.0.0.1` | Bind address for the HTTP transport |
| `MCP_PORT` | `3201` | Port for the HTTP transport (the reference deployment uses 8005 behind a proxy) |
| `MCP_AGENT_ID` | unset | Fallback identity for writes when no `X-Agent-ID` header is present |
| `MCP_OAUTH_ENABLED` | unset | Enables the OAuth2 resource-server layer for MCP clients |
| `MCP_UI_ENABLED` | unset | Serves the lightweight server-rendered board in the same process |
| `ORC_ADMIN_USER` / `ORC_ADMIN_PASSWORD` | unset | Seeds the first admin on boot, when no user exists |
| `ORC_COOKIE_SECURE` | auto | Forces the session cookie's `Secure` flag independently of `X-Forwarded-Proto` |

The previous prefix is still read as a fallback: `TASK_ORCHESTRATOR_DB` and `TASK_ORCHESTRATOR_CONFIG`
work when the `ORC_*` equivalents are absent, with a deprecation notice in the log.

A continuity guard covers the old default: with no env var set, if
`~/.task-orchestrator/tasks.db` exists and `~/.orc/tasks.db` does not, the legacy file is used
(with a one-time warning) instead of starting an empty database.

## Note schemas and gates

A YAML file declares, per item type, which notes each phase requires. A transition is refused
while a required note is missing — that is what makes `done` mean something.

```yaml
# .taskorchestrator/config.yaml
work_item_schemas:
  task:
    lifecycle: auto
    notes:
      - key: requirements
        role: queue
        required: true
        description: "Acceptance criteria before starting"
      - key: done-criteria
        role: work
        required: true
        description: "What does done look like?"
  bug:
    lifecycle: manual
    notes:
      - key: reproduction
        role: queue
        required: true
        description: "Steps to reproduce"
      - key: root-cause
        role: work
        required: true
        description: "Root cause analysis"
```

Lifecycle modes:

| Mode | Behaviour |
|---|---|
| `manual` | Every phase required (default) |
| `auto` | Skips review when no review-phase notes are defined |
| `auto-reopen` | Terminal items reopen when their notes are updated |
| `permanent` | Cannot be cancelled |

## Dependency patterns

Dependencies enforce ordering: a blocked item cannot advance until its blockers reach the
`unblock_at` threshold.

```python
# Linear chain: A before B before C
manage_dependencies(operation="pattern", item_ids="a,b,c", pattern="linear")

# Fan-out: A blocks both B and C (they can run in parallel afterwards)
manage_dependencies(operation="pattern", item_ids="a,b,c", pattern="fan-out")

# Fan-in: both A and B must finish before C
manage_dependencies(operation="pattern", item_ids="a,b,c", pattern="fan-in")

# Early unblock: unblock when the blocker reaches review instead of done
manage_dependencies(operation="add", from_id="a", to_id="c", unblock_at="review")
```

Cycle detection rejects circular edges. The `relates_to` type creates an informational link that
does not block anything.

## Workspaces

A workspace is a tag-scoped view: tag groups, repository hints, conventions and memory tags.
Queries accept a workspace to return only what belongs to it, which is how a subagent receives
context for one project without another project's noise.

## Deployment notes

- The HTTP transport needs the optional `ui` extra (`fastapi` + `uvicorn`): a plain install does
  not pull it in, and `orc-serve` (the streamable-http entry point) fails at import. Clean
  install: `uvx --from 'orc-hestrator-server[ui]' orc-serve` (or `uv tool install
  'orc-hestrator-server[ui]'` then `orc-serve`); from a checkout: `uv sync --extra ui` then
  `uv run orc-serve`.
- `deploy/orc.service` + `deploy/orc.env.example` provide a user-level systemd unit and the
  environment template for running `orc-serve` as a service.
- Serve the SPA under a subpath by building with `--base=/ui/` and setting `VITE_API_BASE=/api`;
  proxy `/api/` to the backend.
- Put a TLS proxy in front. The edge credential (basic auth) is a barrier for agents; the human
  session cookie carries the UI's own authentication.
- Health check: `GET /health` returns `{status, version, uptime_seconds}` and needs no auth.
