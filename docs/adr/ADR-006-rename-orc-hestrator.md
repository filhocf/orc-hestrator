# ADR-006 — Rename to orc-hestrator

**Status:** accepted (2026-10-18, Claudio)
**Deciders:** Claudio, T'Pol
**Related:** ADR-001 (central service), docs/specs/SPEC-rename-orc-hestrator.md

## Context

The project was published as `task-orchestrator-py`, described in the repository as a Python
port of a Kotlin project, while the product presented itself as `task-orch`, "Produto X" and
`Orc[hestrator]` in the design system. Four names, one product, none of them the name people
actually say.

The obvious candidates were evaluated for availability before deciding:

| Name | PyPI | npm | GitHub (search by name) | Web |
|---|---|---|---|---|
| `orc` | taken (web framework) | — | populated | highly populated in the agent space |
| `orc-mcp` | free | taken (`@karowanorg/orc-mcp`) | — | — |
| `mcp-orc` | free | — | taken (`szautkin/mcp-orc`) | — |
| `mcp-orchestrator` | taken (different scope) | — | — | — |
| `orc-hestrator` | free | free | zero repositories | zero occurrences |

Domains were checked by RDAP against the official IANA bootstrap endpoints, with a control query
to prove the endpoint answers (`google.dev` and `google.com` both return 200, so a 404 means the
name is unregistered, not that the query failed):

`orc-hestrator.dev`, `.ai`, `.io` and `.com` are all free, confirmed by DNS NXDOMAIN for the
first three.

## Decision

The product name is **Orc[hestrator]**, "Orc" for short. The identifier that carries the brand
is the pun, not a generic word.

- PyPI distribution: `orc-hestrator`. Install with `uvx orc-hestrator`.
- Console scripts: `orc` and `orc-ui`.
- MCP server name reported in `initialize`: `orc`.
- Canonical site: `orc-hestrator.dev`, with `.com` and `.ai` as defensive registrations.
- Environment variables: `ORC_DB`, `ORC_CONFIG`, `ORC_LANG` become primary.
- Repository: `filhocf/orc-hestrator` (GitHub keeps redirects from the old name).
- The Python import package stays `task_orchestrator` for now. Nobody importing an MCP server
  uses the module path, and renaming it touches 96 files for cosmetic gain — risk without
  payoff. If it ever needs to align, it is a separate change with a deprecation shim.

## Compatibility

Two releases of overlap, then the old names are retired:

1. `orc-hestrator` is published with `orc`, `orc-ui`, `orc-mcp` scripts, and keeps
   `task-orchestrator-py` / `task-orchestrator-ui` as aliases that emit a deprecation notice
   on stderr.
2. The old environment variables keep working as fallbacks (`TASK_ORCHESTRATOR_DB`,
   `TASK_ORCHESTRATOR_CONFIG`), with `ORC_*` taking precedence and a warning naming the
   replacement.
3. A final `task-orchestrator-py` release is published whose description states that the
   project is now `orc-hestrator`, so anyone upgrading by habit lands on the new package.

## Consequences

- Every client configuration must change: the config key and the script name. Documentation,
  the onboarding text served by the MCP tool, CI, and the systemd unit need to agree, which is
  why this is one slice (F7) and not a rename performed file by file.
- The MCP tool prefix in clients follows the server name; clients that pin the old prefix need
  to re-read tools. Recorded in the CHANGELOG.
- `CHANGELOG.md` keeps the old name for every historical release; the README carries a single
  "formerly published as" line. History is not rewritten.
- The `.dev` TLD is HSTS-preloaded, so the canonical site is HTTPS-only by construction, which
  matches the product's security posture rather than fighting it.
