# Product Requirements — Orc[hestrator]

Status: living document. Canonical language: English.
Supersedes: the root `PRD.md` feature checklist and `docs/PRD-X.md` (the provisional "Product X"
document). Neither is kept; this file is the single product statement.

## 1. Problem

Three failures compound when AI agents do real work.

**State does not survive the agent.** Context compacts, the session ends, the operator switches
machines — and the agent no longer knows what was done, what is blocked, or what comes next.

**Coordination is blind across machines.** Session registries know who is active on the machine
they run on. An agent on another host, or a second agent in another terminal, is invisible. The
measured cost is real: two machines spent an hour implementing the same feature.

**State depends on the operator's discipline.** Items sit in `done` with an unmerged branch, WIP
inflates because nobody closes anything, work done directly in a terminal never becomes an item.
Every tool that asks a human to remember will be wrong within a week.

Underneath all three: there is no shared, trusted place where a human and N agents see the same
work, at the same time, with the same rules.

## 2. Vision

One service where every agent, on any machine, and the human connect to the same work state:
items, arcs, dependencies, gates — and who is working on what, right now.

Agents operate over MCP. The human operates over a web UI. State is a single source of truth, not
copies that diverge. External events move items, so the operator does not have to remember.

## 3. Personas

1. **The operator agent** — the primary user. Pulls the next item, claims it, advances it, records
   evidence, sees who else is active. Runs as a CLI agent or as a subagent.
2. **The human lead** — reads the board, intervenes at gates, sets priority, reconciles. Enters
   through the UI, not through the terminal.
3. **The ephemeral subagent** — receives workspace context, claims one item, executes, reports,
   ends. Must never inherit another task's context.

## 4. Principles

- **The human owns the gates; the agent operates between them.** Authority is a function of state,
  not of hierarchy. This resolves the standing tension between an agent's throughput and a
  human's judgment without subordinating either.
- **Backend first, UI second.** A UI over a backend that lies is a beautiful lie. The order is
  trustworthy state → event automation → rich MCP surface → UI.
- **Automation over discipline.** As much state as possible is captured by event (git, CI, deploy),
  not by someone remembering to click.
- **One source of truth.** A local database that diverges is a defect, not a feature. Offline is
  an explicit later stage, added only if measured pain justifies it.
- **The agent is a first-class actor.** Its identity, presence and claims are properties of the
  work, not of a separate system.
- **Compatible with what already runs.** Existing workflow, workspaces, dependencies and gates
  keep working. Evolution, not rupture.
- **Kanban is native; Scrum is a profile.** Continuous flow with pull-based claims is the natural
  physics for human-plus-agent work. Timeboxed ceremonies are configurable and never mandatory.

## 5. What exists today

Shipped and in production use:

- Work items with hierarchy (four levels), priority, complexity, tags, due dates, scheduling.
- Enforced state machine `queue → work → review → done` with triggers and structured errors.
- Dependency graph with cycle detection and a configurable unblock threshold.
- Phase notes with YAML schemas that gate transitions.
- Workspaces, metrics, graph analytics (critical path, impact, bottlenecks).
- Archive, checkpoints, export/import, full-text search.
- Central presence: `hostname / agent_id / session_id`, heartbeat, stale reaping.
- Claims on work items or free-form resources, with conflict detection.
- Per-request agent attribution recorded on every write.
- REST API, user authentication with RBAC, OAuth2 resource-server mode for agents.
- React management UI: nine screens, dark and light themes.
- Onboarding served by the server itself, internationalized (English canonical, pt-BR second).

## 6. Next

| Area | Intent | Why now |
|---|---|---|
| Event ingestion | Git, CI and webhooks move items | Removes the biggest remaining dependency on discipline |
| Typed gates | Blocking predicates: CI status, coverage, approver role, no bypass | A gate that can be skipped is theatre |
| Work-item types | First-class incident and spike flows | Real work is not only features |
| Claim leases | TTL on claims | A dead agent must not hold an item forever |
| Authoring UI | Create and edit items in the browser | The UI currently reads more than it writes |
| Hybrid mode | Local primary, central secondary | Only if offline pain is measured |

## 7. Non-goals

- **Agent runtime orchestration.** Orc does not spawn or supervise agent processes. Agents run
  where they already run.
- **Memory.** Facts belong to a memory service. Orc stores the structure of work and who is doing
  it. The two compose.
- **Replacing the human's judgment.** Orc makes state and gates explicit; it does not decide
  priorities for the team.
- **Corporate multi-tenancy in v1.** Organization-level SSO, orgs and portfolio management are a
  separate instantiation concern.

## 8. Success metrics

- **Trust:** zero structurally divergent boards. There is one source, so there is nothing to
  diverge.
- **Coordination:** zero duplicate work across machines, measured by claims and by incidents
  where two agents touch the same item.
- **Maintenance cost:** time per session spent reconciling or cleaning WIP trends to zero.
- **Attribution:** every write carries a real `agent_id`; anonymous writes go to zero.
- **Automation:** the share of transitions triggered by events rather than by humans rises.

## 9. Open questions

1. **Protecting the human from the comparison.** Orc exposes that an agent completes ten times
   faster. Should the product normalize units and separate the human lens, or show raw data and
   let the organization draw its own conclusion? This is a values decision, not a technical one.
2. **Gate typing depth.** Which predicates are worth shipping first: CI status, coverage,
   required approver, or an expression language?
3. **Offline.** How much real pain must be measured before the hybrid mode earns its complexity?

## 10. History of this document

The product was designed as a merge of a task orchestrator and a session registry, reviewed by a
panel of thirteen independent roles (six human, seven machine), and validated in production on a
single-operator fleet of agents across three machines. The decision records live in `docs/adr/`;
the requirements per slice live in `docs/specs/`.
