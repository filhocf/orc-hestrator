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

## Gate

- G0–G6 per DEVELOPMENT-STANDARDS §8. The gate is a board item with an owner,
  not an implicit phase.
- One item = one commit = one measured AC = one status transition.
- Delegation is triggered by reading, not by size: if the next step needs a file
  the orchestrator has not read, it is a subagent with a surgical brief.
- The orchestrator does not implement. Deviation requires a named cause
  (unavailable model, dead subagent, missing tool) recorded in the report.
