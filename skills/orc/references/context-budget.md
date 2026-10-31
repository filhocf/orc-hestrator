# Context budget — keep reads cheap

The board history is resent to the model on every turn. In a long session the
dominant cost is navigation (reading the board), not the work itself. Orc makes
the cheap path the explicit one: **reads start compact; full needs a reason.**

## Measured cost (real board)

| Call | Tokens | Payload shape |
|---|---|---|
| `get_next_item(compact=True)` | ~49 | id (8 chars), title (≤60), status, priority, due_at, `reason` |
| `get_context(verbosity="compact")` | ~331 | counts, next_item, active/blocked/stale as `[id,title,status,priority,stale_days]`, stale capped at 10 with `stale_total` |
| `query_items(compact=True)` | ≤150 chars/item | `{items, count, has_more, next_offset}` — explicit paging |
| `get_context()` full | ~34318 | whole rows for every item |

Two orders of magnitude separate compact from full. That is the whole point.

## Verbosity levels of `get_context`

- `compact` — counts + next_item + truncated active/blocked/stale lists. Session
  start and status checks.
- `standard` — compact plus each item's `description` truncated to ≤200 chars.
- `full` (default) — whole rows. Use only when inspecting one specific item, and
  prefer `get_context(item_id=...)` for that, which is always full for the one item.

## Rules of thumb

1. `get_next_item(compact=True)` on every turn to decide what to do next.
2. `get_context(verbosity="compact")` to resume or to report status.
3. `query_items(compact=True)` to scan; page with `next_offset`.
4. Ask for `full` only when you are about to act on a specific item.
5. Project columns with `fields="id,title,status"` when you need just a few.

## Why a human cares

The same compact-first discipline keeps the UI responsive and the session legible.
Cost and quality move together: a smaller, well-managed window means less
re-prompting and clearer reasoning, not just a cheaper bill.
