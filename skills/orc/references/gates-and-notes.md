# Gates and notes

## What a gate is

A transition (`advance_item(item_id, trigger)`) only succeeds when both hold:

1. **Dependencies satisfied** — every blocker has reached its `unblock_at`
   threshold.
2. **Required notes present** — a note schema may require a note (by key, for a
   phase) before a given transition.

The engine rejects anything else. Never try to bypass it from an adapter — the
state machine is the source of truth.

## Previewing without side effects

`get_next_status(item_id, trigger)` returns `can_advance`, the current and next
status, and any blockers. Use it to check feasibility before you act. (Preview
covers `start`/`complete`/`block`/`cancel`/`reopen`/`resume`; for a pause use
`block` — `hold` is its alias on `advance_item` but not on `get_next_status`.)

## Notes

Notes are keyed documentation attached to an item, tagged by phase `role`
(`queue`, `work`, `review`):

```python
manage_notes(operation="upsert", item_id="a1b2", key="requirements",
             role="queue", body="EARS-style acceptance criteria")
manage_notes(operation="upsert", item_id="a1b2", key="done-proof",
             role="review", body="what shipped + how it was verified")
manage_notes(operation="list", item_id="a1b2")
```

Use notes for requirements, done-criteria, decisions and handoff context — the
things the next agent (or the human) needs. Do **not** use the board as a
conversation diary; that bloats every read.

`query_notes(item_id, key, include_body=false)` gives token-efficient metadata
when you only need to know which notes exist.

## Note schemas

`manage_schemas`:

- `list` — all loaded schemas.
- `get <name>` — one schema.
- `check <item_id>` — gate status for an item (which required notes are missing).
- `reload` — reload from the config file (`ORC_CONFIG`).

If a `complete` is refused with a note-gate error, run `manage_schemas(check,
item_id=...)` to see exactly which keyed note the schema requires.
