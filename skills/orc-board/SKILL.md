---
name: orc-board
description: >-
  Use the Orc MCP server to run your own work: resume a session, find the next
  actionable item, and move items through queue → work → review → done with notes
  that survive context loss. This is the day-to-day cycle any agent follows when
  Orc is its board. Use it at session start, when picking what to do next, when
  finishing a task, or when you get blocked. For shaping the backlog (arcs,
  hierarchy, dependencies) use orc-modeling; for multi-agent presence and claims
  use orc-presence.
license: MIT
metadata:
  author: Claudio Ferreira Filho - github.com/filhocf
  version: "1.0.0"
  keywords: "orc, orchestrator, task, work item, board, session resume, next item, queue, work, review, done, advance_item, get_context, get_next_item, manage_notes, note gate, trigger, workflow, mcp"
---

# orc-board — running your work on Orc

Orc is an MCP server that holds work items, dependencies, gates, agent presence
and claims in one place. This skill is the **day-to-day cycle**: how you resume,
decide what to do, do it, and close it without losing state.

The state machine is fixed: **queue → work → review → done**. You never edit
status directly; you fire a **trigger** and the engine decides.

## CRITICAL — the three reflexes

1. **Start every session with `get_context`.** Never act on memory of where you
   were. The board is the source of truth, not your recollection.
2. **A green test is not a closed gate.** Before `complete`, confirm the real
   acceptance criterion. Leave the evidence in a note.
3. **Notes outlive you.** When your context is compacted or another agent takes
   over, the only thing that carries the work forward is the note. Write it as if
   someone else will finish the task.

## Session start — resume in two calls

```
get_context(verbosity="compact")      # counts + active + blocked + stale, ~300 tokens
get_next_item(compact=True)           # the single best next thing, ~50 tokens
```

`get_context` without arguments is the global dashboard. With `item_id` it is the
detail of one item (children, notes, blockers, `can_advance`). Use
`verbosity="compact"` for the dashboard — `full` returns whole rows and is for
humans/debugging, not for an agent turn.

`get_next_item` returns the highest-priority item with no unsatisfied
dependencies. `compact=True` adds a `reason` ("in progress" / "overdue" /
"priority:<level>") so you know *why* it won the queue. Ask for the full item only
when you are about to work on it.

## The cycle — one trigger at a time

Triggers for `advance_item`: `start` (next phase), `complete` (jump to done),
`block`/`hold` (pause), `resume` (unblock), `cancel` (close), `reopen`
(done/cancelled → queue).

```
advance_item(item_id=X, trigger="start")     # queue → work: you are now doing it
# ... do the work ...
manage_notes(item_id=X, operation="upsert", role="work",
             key="done-criteria", body="what proves this is done + evidence")
advance_item(item_id=X, trigger="complete")  # → done
```

**Preview before you move.** `get_next_status(item_id=X, trigger="complete")` is
read-only: it returns `can_advance`, the current and next status, and any
blockers, with no side effect. Use it when you are unsure a transition is legal
(dependency not yet satisfied, note gate unmet).

**Batch transitions** when closing several at once:
`advance_item(transitions_json=[{"item_id":"a","trigger":"complete"}, ...])`.

## Notes — the memory of the work

`manage_notes` keeps persistent documentation per phase. `role` ∈ {queue, work,
review} marks which phase the note belongs to. Operations: `upsert` (create or
update by `key`), `delete`, `list`.

Write a note when you:
- capture a decision or a done-criterion (`role="work"`, `key="decision"`);
- resolve something and want the resolution searchable (`key="resolucao"`);
- hand off — the next agent reads `query_notes(item_id=X)` and continues.

Some transitions require a note (a **note gate** — see `manage_schemas`, covered
in orc-modeling). If `advance_item` refuses with a missing-note error, add the
required note and retry. Do not try to bypass the gate from the adapter.

## When you get blocked

```
advance_item(item_id=X, trigger="block")
manage_notes(item_id=X, operation="upsert", role="work",
             key="blocker", body="what is blocking and what would unblock it")
```

When the blocker clears, `trigger="resume"`. If a dependency is what blocks you,
do not force it — fix or advance the blocker (see orc-modeling for dependency
mechanics).

## Short-lived interruptions — the context stack

For a quick detour (<5 min) without losing your place:

```
advance_item(item_id=CURRENT, trigger="hold")
manage_notes(item_id=CURRENT, operation="upsert", role="work",
             key="execution-state",
             body='{"last_action":"...","next_step":"...","files":["..."]}')
# handle the detour
advance_item(item_id=CURRENT, trigger="resume")
```

`get_execution_stack` shows the nesting if you hold items on top of items. Keep it
shallow (max 4 levels of hierarchy anyway).

## Pitfalls (measured, not theoretical)

- **`get_next_item` returns containers.** It does not distinguish an arc/epic
  (a parent) from a leaf, so it may hand you the umbrella as "next". Read the
  item: if it has children, drill in with `query_items(operation="children")`
  instead of starting the container.
- **`hold` sends the item to `blocked`.** There is no distinct "paused" status;
  operator-pause and waiting-on-dependency share the `blocked` state. Use the
  note to record *why* it is blocked so the distinction is not lost.
- **`verbosity="full"` / non-compact lists are expensive.** The schema already
  costs ~7k tokens per connection; do not also pull full rows every turn. Default
  to `compact`.
- **Identity is per-request.** If writes land with `created_by: null`, your
  session is not registered — see orc-presence.

## Self-teaching surface (when in doubt, ask the server)

Orc ships its own onboarding. If you are unsure how this client should behave:

- `orc_onboarding(client_type="kiro", lang="en")` — a read-only guide tailored to
  the client (hermes / kiro / cli), no database touched.
- MCP resources: `orc://workflow`, `orc://glossary`, `orc://onboarding`
  (each with a `/pt-br` variant).
- MCP prompts: `session_start`, `quick_start`, `work_summary`,
  `status_progression`, `batch_complete`, `dependency_manager`,
  `create_item_from_context`.
