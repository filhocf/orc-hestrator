# ADR-007 — Transport chosen by entry point, not by environment variable

**Status:** accepted (2026-10-18, Claudio)
**Deciders:** Claudio, T'Pol
**Related:** ADR-001 (central service), docs/specs/SPEC-rename-orc-hestrator.md (F7)

## Context

The server supports two transports: `stdio` and `streamable-http`. Today the choice is
`MCP_TRANSPORT`, defaulting to `stdio` in code and set to `streamable-http` only by the deployment
unit that lives on one machine and is versioned nowhere.

That produces two opposite failure modes:

- **If the default were HTTP**, the primary install path breaks. An MCP client that spawns a
  command (`uvx orc-hestrator`) waits for a handshake on the child's stdin while the server binds a
  port and stays silent. The user concludes the product is broken.
- **As it stands**, the central deployment depends on somebody remembering to export a variable.
  Stdio cannot cross a network at all: no URL, no TLS, no headers. A process started without the
  variable serves nothing a remote client can reach.

Both "make stdio the default" and "make HTTP the default" are wrong, because the transport is not a
global preference — it is a property of how the process was started.

## Decision

The transport is selected by the entry point:

| Command | Transport | Use |
|---|---|---|
| `orc` | stdio | The command an MCP client spawns locally |
| `orc-serve` | streamable-http | The central service: VPS, container, systemd |
| `orc-ui` | — | The lightweight server-rendered board |

`MCP_TRANSPORT` remains available as an override for tests and edge cases, but it is no longer the
mechanism a deployment relies on.

Deployment artifacts are versioned in `deploy/`: a systemd user unit and an environment example.
The unit's `ExecStart` calls `orc-serve`, so the transport cannot be forgotten.

## Consequences

- A new user gets the right behaviour without knowing what a transport is: local clients point at
  `orc`, the host runs `orc-serve`.
- Removing the environment variable from the critical path removes a class of support question
  ("why does my remote client see nothing?").
- The container image, when it exists, exposes HTTP only, and the local case never runs in a
  container.
- Two console scripts must stay in sync with the server name reported in `initialize`
  (`orc`) — checked by the F7 acceptance criteria.
- `deploy/` enters the repository, so the deployment stops being tribal knowledge on one machine.
