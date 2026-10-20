# Conventions

Decisions that get re-litigated because nobody wrote them down. Each entry is
either a **rule** (violating it is a defect) or a **practice** (current habit,
open to change). Update this file when a decision is made in conversation —
that is the whole point of it.

Related: `AGENTS.md` (architecture), `docs/specs/` (requirements),
`~/git/conhecimentos-de-ia/padroes/DEVELOPMENT-STANDARDS.md` (the gate).

## Language

| Artifact | Language | Kind |
|---|---|---|
| `CHANGELOG.md` | English | rule — it ships to PyPI and is read by international users |
| `README.md`, `AGENTS.md`, public docs | English | rule |
| Code, docstrings, comments | English | rule |
| `docs/specs/*.md` (requirements, EARS) | PT-BR | rule — internal, read by Claudio |
| Commit messages | PT-BR subject and body | practice |
| Board items and notes | PT-BR | practice |

## CHANGELOG

- Keep a Changelog sections only: Added / Changed / Deprecated / Removed /
  Fixed / Security. One line per change, phrased as the effect on the consumer.
- Rationale, gate history and migration steps do **not** belong here — they go
  to the spec and the PR. One number per entry, only when the number *is* the
  argument.
- Full rule: DEVELOPMENT-STANDARDS §9.0.2.

## Measurement and proof

- Every number carries its environment ("bench, 64-item plate" × "production,
  real board").
- Acceptance criteria are provisional until measured on real data; if the real
  measurement misses the ceiling, the decision is explicit — fix the design or
  correct the criterion with the measurement attached. Never relax silently.
- A temporary verification script is ad-hoc evidence, never a substitute for the
  suite. Both are reported separately.

## Board hierarchy

One product, one root. Work items never live at the root.

```
ARC: <product>            # one per product (Orc, QueryFlow, mms, DAIA…)
  RELEASE <version>       # sub-arc per released or planned version
    <slice>               # work item with a measured AC
  SUB-ARC: <area>         # ongoing work without a version (refactor, backlog)
  <ad-hoc>                # loose product task (site, CI, migration)
```

- Max depth is 4 (product → version → slice → subtask). A fifth level means the
  slice was too big.
- A finished version keeps its `RELEASE` sub-arc; do not flatten features into
  the product arc after the fact.
- The board is shared across projects; the UI must scope the arc tree by
  workspace or by selected root, never show every product at once.

## Gate

- G0–G6 per DEVELOPMENT-STANDARDS §8. The gate is a board item with an owner,
  not an implicit phase.
- One item = one commit = one measured AC = one status transition.
- Delegation is triggered by reading, not by size: if the next step needs a file
  the orchestrator has not read, it is a subagent with a surgical brief.
- The orchestrator does not implement. Deviation requires a named cause
  (unavailable model, dead subagent, missing tool) recorded in the report.
