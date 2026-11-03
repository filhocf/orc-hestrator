---
name: orc-modeling
description: >-
  Shape a backlog in Orc so it reads as a plan, not a bucket of tasks. Use when
  you organize work into arcs and sub-arcs, set execution order with dependencies,
  consolidate duplicate or stale items, or clean up a tree that grew unmanaged.
  Covers the one-arc rule, the four-level hierarchy, dependencies as a backbone
  (blocks / unblock_at), note gates, and anti-bucket hygiene. For the day-to-day
  work cycle use orc-board; for multi-agent presence use orc-presence.
license: MIT
metadata:
  author: Claudio Ferreira Filho - github.com/filhocf
  version: "1.0.0"
  keywords: "orc, backlog, arc, sub-arc, hierarchy, parent_id, reparent, dependencies, manage_dependencies, blocks, unblock_at, backbone, execution order, consolidate, merge, cleanup, note gate, manage_schemas, workspace, tags, hygiene"
---

# orc-modeling — shaping a backlog that reads as a plan

A backlog in Orc is a graph: items in a hierarchy (`parent_id`, max 4 levels)
plus dependency edges (`from_id` **blocks** `to_id`). Priority alone
(critical/high/medium/low) does **not** give you order — it ranks, it does not
sequence. Without dependencies, an arc looks like a full bucket: you cannot see
what comes first or what is the end. This skill is how you give it a spine.

## CRITICAL — the shape rules

1. **One arc per project, everything else is a sub-arc under it.** Do not let a
   project grow a second top-level arc. If you find siblings that are really the
   same effort, reparent them in and renumber (`SUB-ARC N: ...`). Redundant
   top-level arcs are the main cause of "I can't see what we have".
2. **Priority ranks, dependencies sequence.** If you want the board to show
   before/after, you must add dependency edges. Nothing else encodes order.
3. **A container must not block its own child in progress.** Before adding an
   edge A → B, check that B is not already `work`. An edge onto an active item
   can freeze it. Model the order between *sibling sub-arcs*, not onto the leaf
   you are already executing.

## Hierarchy — reparent and consolidate

`manage_items` does the structural work:

```
# move an item under an arc (and rename to the sub-arc convention)
manage_items(operation="update", item_id=X,
             parent_id="<arc-id>", title="SUB-ARC N: ...")

# unparent
manage_items(operation="update", item_id=X, parent_id="none")

# batch create children
manage_items(operation="create", items_json=[{...}, {...}])

# delete (use recursive=true to drop descendants too)
manage_items(operation="delete", ids_json=["id1","id2"], recursive=true)
```

**Consolidation playbook** (merging an old arc into the canonical one):
1. Read the stray arc and its children in full
   (`query_items(operation="get"/"children", fields=...)`).
2. For each child, decide: **keep** (reparent in), **merge** (fold into an
   existing equivalent and delete the duplicate), or **drop** (cancel/delete if
   obsolete — e.g. a dated "present tomorrow" task whose date has passed).
3. Reparent the arc itself as a sub-arc; renumber for a single clean sequence.
4. Close what is already resolved: `advance_item(trigger="complete")` with a
   resolution note pointing to the evidence, rather than leaving it in queue.

Watch the **4-level limit**: Arc → sub-arc → task → subtask. If a reparent would
go deeper, flatten instead.

## Dependencies — the execution backbone

`manage_dependencies` with `operation="add"` creates `from_id` **blocks**
`to_id`. The key parameter is **`unblock_at`** ∈ {done, review, work}: the status
the blocker must reach before the blocked item frees.

```
manage_dependencies(operation="add", from_id=A, to_id=B, unblock_at="review")
```

**Use `unblock_at="review"` for a macro backbone between sub-arcs.** It lets the
next sub-arc start as soon as the previous one reaches review, instead of waiting
for a full `done` — the spine guides order without serializing everything hard.

**Model few, high-value edges.** A backbone across ~10 sub-arcs is readable and
maintainable. Wiring every leaf into a web is not — inside a sub-arc, let
priority + one or two genuine edges carry the order.

Inspect and repair:
```
query_dependencies(item_id=X, direction="both", neighbors_only=true)   # fast, direct edges
query_dependencies(item_id=X, neighbors_only=false)                     # full BFS graph
manage_dependencies(operation="remove", from_id=A, to_id=B)             # undo a wrong edge
```

`add` returns `CONFLICT` if the edge already exists — that is informative, not an
error; part of your intended backbone may already be in place. Query first if you
are unsure. The engine rejects cycles.

Read the result with `get_blocked_items` — items that appear there are waiting on
the backbone; items absent from it are the entry points free to start now.

## Note gates — making a phase require evidence

`manage_schemas` attaches a required-note schema to a transition, so an item
cannot advance past a phase without the documented evidence. Use it to enforce a
Definition of Done on a class of items. When present, `advance_item` refuses with
a structured missing-note error naming the field; satisfy it with `manage_notes`
(see orc-board) and retry. Do not weaken the gate to get past it.

## Hygiene — anti-bucket discipline

- **Search before you create.** `query_items(operation="list", search="...")`
  to avoid duplicates.
- **Every item carries at least one project tag.** Domain separation in Orc is by
  **tag**, not by named workspace (`manage_workspaces` configures scoped tag
  views, but there is no "dtp"/"pessoal" workspace to pass around).
- **Stale items decay.** An item sitting in `work` with no progress is noise;
  demote it to `queue` with a note, or cancel it. A tree with a long stale list
  is telling you the backbone or the scope is wrong.
- **Close, don't accumulate.** Resolved work becomes `done` with a note; it does
  not linger in queue as a false "to do".

## Example — a clean consolidation (shape of what good looks like)

```
# one arc survives; strays become numbered sub-arcs
manage_items(update, item_id=<v0.2 epic>,  parent_id=<ARC>, title="SUB-ARC 9: ...")
manage_items(update, item_id=<aiops epic>, parent_id=<ARC>, title="SUB-ARC 10: ...")
# obsolete dated task dies
manage_items(delete, item_id=<"present tomorrow">)
# resolved question closes with evidence
manage_notes(upsert, item_id=<layout decision>, role="queue", key="resolucao",
             body="resolved in lab on <date>: chose X; proof: validate exit 0")
advance_item(item_id=<layout decision>, trigger="complete")
# backbone between sub-arcs (unblock at review, not done)
manage_dependencies(add, from_id=<scope arc>, to_id=<build arc>,  unblock_at="review")
manage_dependencies(add, from_id=<build arc>, to_id=<pilot arc>,  unblock_at="review")
```
