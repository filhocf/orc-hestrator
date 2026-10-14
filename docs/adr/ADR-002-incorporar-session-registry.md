# ADR-002 — Incorporar o session-registry como sub-domínio do task-orch

**Data:** 2026-10-14 · **Status:** Aceito · **Decisores:** Claudio, Zero

## Contexto

`mcp-session-registry` é um serviço MCP separado que faz presença de agentes (register,
heartbeat, reaping) e claim de recursos (arquivo/branch/**work item**) — mas só
**por-máquina**. O `session_claim` já aceita "work item" como alvo, porém como string
opaca: ele não conhece o work item que vive no task-orch. São dois sistemas falando do
mesmo objeto sem se conhecer. Consequência real: retrabalho (1h perdida implementando um
degrau que outra máquina já reivindicava) — o claim por-máquina não via o item central.

## Decisão

Fundir o session-registry **dentro** do task-orch como dois sub-domínios: **presença**
(`presence.py`) e **claims** (`claims.py`). O claim passa a ser **unificado**:
`claim(subject_type ∈ {work_item, resource}, subject_ref, agent_id, expires_at?)`.
- `work_item` → FK real para `work_items.id` (claim de trabalho de 1ª classe).
- `resource` → string livre (arquivo/branch) — **preserva** o caso original.

## Razão

- Conceitualmente são a mesma coisa: "N agentes como atores" = presença + claim. O
  session-registry já é um pedaço do produto que a RFC-001 descreve (`State` = "quem está
  fazendo o quê agora"), separado por acaso histórico.
- Com a VPS central (ADR-001), erguer **1 serviço** que faz trabalho + presença é melhor
  que **2** — menos superfície, menos deploy, uma fonte de verdade.
- "Quem está no item" vira **propriedade consultável do item**, não de um sistema à parte
  → mata o retrabalho cross-máquina na origem.
- O esforço não é novo: session-registry central já era déficit listado (RFC-001 §13).
  Incorporar **realoca** o trabalho, não adiciona.

## Consequências

- ✅ `get_next_item` pode mostrar "DNBSCDC289 está neste item desde 14h".
- ✅ Um serviço na VPS, não dois.
- ✅ Não perde o caso de claim de recurso avulso (arquivo).
- ⚠️ `mcp-session-registry` (repo separado) é **aposentado/absorvido** — comunicar e
  migrar seus consumidores para as tools novas do task-orch.
- ⚠️ Presença agora é cross-máquina (central), não local — muda a semântica de "stale"
  (reaping passa a considerar heartbeat de qualquer máquina).

## Alternativas descartadas

- **Manter dois serviços e integrá-los por chamada**: mais superfície, dois deploys, duas
  fontes de verdade. Descartado.
- **Session-registry central separado** (só tornar ele cross-máquina): resolveria presença
  mas manteria o claim de work item como string opaca, sem FK. Perde o ganho principal.
