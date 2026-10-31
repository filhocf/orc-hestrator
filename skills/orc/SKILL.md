---
name: orc
description: >-
  Operate the Orc work board from an AI agent: register presence, create and
  advance work items, gate transitions with notes, claim work to avoid
  collisions, and keep reads cheap. Use when you track multi-step work across
  sessions or machines, coordinate more than one agent, or need the human to
  see what you are doing. Triggers: "track this work", "what's next on the
  board", "create a work item", "advance/complete this item", "who's working
  on what", "claim this before I touch it".
---

# Orc — operating the shared work board

Orc is an MCP server that keeps work items, dependencies, gates, agent presence
and claims in one place. You, the agent, operate it through MCP tools; the human
watches the same state through a web UI. One truth, two views.

Orc is **not** an agent runtime (it does not spawn agents) and **not** a memory
system (memory stores facts; Orc stores the structure of work).

## Mental model

A **WorkItem** is a unit of work with `title`, `status`, `priority`
(critical/high/medium/low), `complexity` (1-10), `tags`, notes and `due_at`.
Items form a graph: a parent/children **hierarchy** (max 4 levels) plus directed
**dependencies**.

Status flow: `queue → work → review → done`, with auxiliary `blocked` and
`cancelled`.

Convention that matters for navigation: an item **with children is a container**
(an arc/epic); an item **without children is a task**. You work tasks, not
containers.

## The first rule: reads start compact

The board is resent to the model every turn, so in a long session most of what
you pay is navigation, not work. Default to compact; ask for full only when you
are about to act on a specific item.

| Call | Cost (real board) | When |
|---|---|---|
| `get_next_item(compact=True)` | ~49 tokens | every turn — "what's next" |
| `get_context(verbosity="compact")` | ~331 tokens | session start, status check |
| `query_items(compact=True)` | ≤150 chars/item, paged | scanning a list |
| `get_context()` full | ~34318 tokens | only to inspect one specific item (prefer `get_context(item_id=...)`) |

Full details and more recipes in [references/context-budget.md](references/context-budget.md).

## The session cycle

```
agent_register(cli=...)            → returns session_id — REUSE it every call
  claim(subject_type="work_item", subject_ref=<id>, session_id)
  advance_item(<id>, "start")
  ... work, manage_notes ...
  advance_item(<id>, "complete")
  release(...)                      (or let agent_end cascade)
agent_heartbeat(session_id)        every 2-3 min (sessions stale >300s are reaped)
agent_end(session_id)              on exit — releases your claims in CASCADE
```

Identity is the triple `hostname / agent_id / session_id`. Your `agent_id` comes
from the `X-Agent-ID` header (or `MCP_AGENT_ID`); without it, writes are recorded
as an anonymous author. See [references/identity-and-presence.md](references/identity-and-presence.md).

## The eight tools you actually use

| Tool | For |
|---|---|
| `get_context` | dashboard, or the detail of one item |
| `get_next_item` | highest-priority item with no unsatisfied dependency |
| `manage_items` | create / update / delete; batch and hierarchy |
| `create_work_tree` | root + children + dependency wiring in one call |
| `advance_item` | move an item through a trigger, with enforcement |
| `manage_notes` | phase notes, including the ones gates require |
| `agent_register` / `agent_heartbeat` / `agent_end` | presence lifecycle |
| `claim` / `release` / `conflicts` | take and free an item or a resource |

31 tools exist; the full generated reference is `docs/TOOLS.md` in the repo.

## Gates: transitions are enforced

Every transition is validated against (1) satisfied dependencies and (2) required
note schemas. A transition only unlocks when all prerequisites are met. Preview
without side effects using `get_next_status(item_id, trigger)`.

Notes are keyed per phase (`queue`/`work`/`review`). A note schema can **require**
a note before a given transition — that is the gate. Use notes to carry
requirements, done-criteria and handoff context, not as a conversation diary.
See [references/gates-and-notes.md](references/gates-and-notes.md).

## Dependencies

`manage_dependencies(add, from_id, to_id, unblock_at)`: `from_id` blocks `to_id`;
`unblock_at` ∈ {done, review, work} says how far the blocker must progress before
the target can move. Cycles are rejected. `create_work_tree` wires a whole tree
atomically with `ref` names.

## Claims: don't collide

Before taking an item, `claim(subject_type="work_item", subject_ref=<id>,
session_id)`. If another session holds it, you get a CONFLICT naming the holder's
triple. You can also claim free-form resources (a file, a branch) with
`subject_type="resource"`. `conflicts(subjects_json, session_id)` checks a batch
before you start.

## A minimal first session

```python
agent_register(cli="your-client")                 # → session_id
get_context(verbosity="compact")                  # cheap board snapshot
get_next_item(compact=True)                        # → the next task (a leaf, not an arc)
claim(subject_type="work_item", subject_ref="a1b2", session_id="...")
advance_item(item_id="a1b2", trigger="start")
manage_notes(operation="upsert", item_id="a1b2", key="done-proof",
             role="review", body="what shipped + how verified")
advance_item(item_id="a1b2", trigger="complete")
agent_end(session_id="...")
```

## Anti-patterns

- Working without a registered session (no `session_id`).
- Grabbing an item without a `claim` — two agents on the same work.
- Creating an item without searching first (`query_items(search=...)`) — duplicates
  poison the graph.
- Reading `full` by habit — use `compact` and pay 100x less.
- Using the board as a chat log.

## Connecting your client

Per-client connection recipes (Hermes, Kiro, Claude, CLI) live in
[references/client-recipes.md](references/client-recipes.md). The server also
teaches itself through the `orc_onboarding(client_type, lang)` tool.

## Troubleshooting

See [references/troubleshooting.md](references/troubleshooting.md): 401 at the
proxy, `ModuleNotFoundError: fastapi`, stdio vs streamable-http, lost identity,
stale sessions.
