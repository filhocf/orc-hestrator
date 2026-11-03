# Orc skills

Agent-facing skills shipped **with the product**. When a client installs the Orc
MCP server, it also gets these skills — they are what replaces the human
explanation of how to drive the board (RFC-002 *Bring Your Agent*, slice F3).

Each skill is a self-contained `SKILL.md` with frontmatter (`name`,
`description`, `license`, `metadata`). The `description` is what a client matches
against to decide when to load the skill, so it is written as triggers, not prose.

## The set

| Skill | When it loads | Covers |
|---|---|---|
| **orc-board** | session start, "what's next", finishing a task, getting blocked | the day-to-day cycle: `get_context`, `get_next_item`, `advance_item`, `manage_notes`, the state machine, read pitfalls |
| **orc-modeling** | organizing the backlog, "too many tasks", setting order | arcs/sub-arcs hierarchy, dependencies as a backbone (`blocks` + `unblock_at`), note gates, anti-bucket hygiene, consolidation |
| **orc-presence** | more than one agent on the same board | identity triple, `agent_register`/heartbeat/end, `claim`/`release`/`conflicts` |

Three skills instead of one because the surface is large (31 tools / 7 prompts /
6 resources): a single file would be a wall the model loads whole on every match.
Splitting by intent keeps each load small and the trigger precise.

## Relationship to the self-teaching surface

The skills are the *proactive* layer; the server also carries a *reactive* one
for when an agent is unsure mid-task:

- `orc_onboarding(client_type=..., lang=...)` — read-only, client-tailored guide.
- resources `orc://workflow`, `orc://glossary`, `orc://onboarding` (+ `/pt-br`).
- prompts `session_start`, `quick_start`, `work_summary`, `status_progression`,
  `batch_complete`, `dependency_manager`, `create_item_from_context`.

Skills teach the habit; the onboarding tool/resources/prompts answer a specific
question on demand. They should agree — when the server surface changes, update
both.

## Authoring

Keep the frontmatter `description` under the embedding limit (~512 tokens),
written as when-to-use triggers. One skill = one dominant intent. The tool names
and arguments in the bodies are derived from `docs/TOOLS.md` (generated from the
server) — when a tool's contract changes, reconcile these skills in the same
change.
