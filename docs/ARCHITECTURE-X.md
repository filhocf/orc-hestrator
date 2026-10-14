# ARCHITECTURE — Produto "X" (task-orch unificado)

> Arquitetura do merge `task-orchestrator-py` + `mcp-session-registry` como serviço
> central. **Data:** 2026-10-14. **Base:** PRD-X.md + RFC-001 §15. **Status:** v0.1 fundação.
> Decisões formais em `docs/adr/`.

## 1. Visão de alto nível

```
┌───────────────────────────────────────────────────────────┐
│                   VPS cfnarede.dev                          │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ nginx (borda)  — basic auth + TLS                    │  │
│  │   https://cfnarede.dev/taskorch                      │  │
│  └───────────────────────┬─────────────────────────────┘  │
│                          │ proxy → 127.0.0.1:PORT          │
│  ┌───────────────────────▼─────────────────────────────┐  │
│  │ task-orch service (FastAPI + MCP StreamableHTTP)     │  │
│  │   OAuth2 (client_credentials)                        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │  │
│  │  │ Work     │ │ Presence │ │ Claims               │ │  │
│  │  │ Engine   │ │ & Agents │ │ (item | resource)    │ │  │
│  │  └──────────┘ └──────────┘ └──────────────────────┘ │  │
│  │        SQLite (WAL) — FONTE ÚNICA                    │  │
│  └──────────────────────────────────────────────────────┘ │
└───────────────────────────┬───────────────────────────────┘
                            │ MCP StreamableHTTP (per-request agent_id)
       ┌────────────────────┼────────────────────┐
       │                    │                     │
 ┌─────▼─────┐        ┌──────▼─────┐        ┌──────▼─────┐
 │ sirdata   │        │ DNBSCDC289 │        │ VPS agents │
 │ Zero(Kiro)│        │ Zero(Kiro) │        │ T'Pol/Scotty│
 │  2º MCP   │        │  2º MCP    │        │            │
 └───────────┘        └────────────┘        └────────────┘
       (SEM banco local — Etapa 1)
```

## 2. Decisões estruturais (resumo; detalhe nos ADRs)

| # | Decisão | ADR |
|---|---------|-----|
| D1 | Serviço central na VPS (fonte única), não SQLite local + sync | ADR-001 |
| D2 | Incorporar session-registry como sub-domínio (presença/claim) | ADR-002 |
| D3 | Fonte única (Etapa 1) → híbrido local+hub (Etapa 2), por etapas | ADR-003 |
| D4 | Segurança: nginx basic auth + OAuth2 no serviço | ADR-004 |
| D5 | `agent_id` per-request (header/`_meta`), não env nem arg | ADR-005 |

## 3. Modelo de dados (unificado)

Herda o schema do task-orch e **absorve** o do session-registry.

### 3.1 Do task-orch (mantido)
- `work_items` (id, title, status, priority, complexity, tags, parent_id, metadata, due_at)
- `dependencies` (from_id, to_id, unblock_at)
- `notes` (item_id, role, key, body) — gates
- workspaces (config), schemas (gates)

### 3.2 Do session-registry (incorporado)
- `agents` / `sessions` — presença: agent_id, hostname, pid, cli, theme, registered_at,
  last_heartbeat, status. (era "session" por-máquina → agora central, chaveado por agent_id)
- `claims` — **unificado**: `claim(subject_type, subject_ref, agent_id, expires_at?)`
  - `subject_type ∈ {work_item, resource}`
  - `work_item` → FK para `work_items.id` (claim de trabalho — resolve retrabalho cross-máquina)
  - `resource` → string livre (arquivo/branch — preserva o caso original do session-registry)
  - `expires_at` → lease temporizado (ideia de task-ledger/llm-bus; opcional v0.1)

### 3.3 Novo
- `agent_id` presente nas operações de escrita (quem criou/avançou/reivindicou).
- (futuro) `events` — log de triggers externos que movem itens.

## 4. Camadas / módulos

```
src/task_orch/
├── server.py        # MCP server (StreamableHTTP) + registro de tools
├── engine.py        # state machine, deps, queries (do task-orch)
├── presence.py      # NOVO: registro/heartbeat/reaping de agentes (do session-registry)
├── claims.py        # NOVO: claim unificado item|resource, conflito, lease
├── db.py            # schema + migrations (fonte única na VPS)
├── schemas.py       # note-gates
├── auth.py          # NOVO: OAuth2 client_credentials + resolução agent_id per-request
└── prompts.py       # context para agentes
```

## 5. Tools MCP (superfície unificada)

Mantém as 22 do task-orch + absorve as 7 do session-registry (adaptadas a central):

| Grupo | Tools |
|-------|-------|
| Trabalho (task-orch) | manage_items, advance_item, manage_dependencies, manage_notes, get_context, get_next_item, query_items, query_dependencies, get_metrics, export/import, ... |
| Presença (ex-session-registry) | agent_register, agent_heartbeat, agent_list, agent_end |
| Claims (unificado) | claim (item\|resource), release, conflicts |

`agent_id` resolvido por requisição (header `X-Agent-ID` / `_meta`), não global.

## 6. Transport e segurança

- **Agentes ↔ serviço**: MCP StreamableHTTP sobre HTTPS. `agent_id` per-request.
- **Borda**: nginx — TLS + basic auth (1ª barreira) → proxy para `127.0.0.1:PORT`.
- **Serviço**: OAuth2 client_credentials (2ª barreira), padrão do hub de memória.
- **Futuro corporativo**: OAuth2 → SSO Keycloak/gov.br (não v0.1).

## 7. Consistência e disponibilidade

- **Etapa 1 (v0.1): fonte única.** CP sobre AP — consistência forte, disponibilidade
  dependente de rede/VPS. Trade-off aceito (ADR-003): sem rede = sem board. Cobre ~95%.
- **Etapa 2 (futuro): híbrido.** Primary local + secondary HTTP (modelo memory-service).
  Offline-capable. Só se o offline doer na prática (medir antes).
- **NÃO há delta-sync** no task-orch — fonte única elimina a necessidade (ADR-003 §razão).

## 8. Deploy

- vps-deploy (skill): uv tool + systemd user service na VPS + nginx reverse proxy.
- Porta interna dedicada (não colidir com memory :8000). Banco em `~/.local/share/task-orch/`.
- Backup: VACUUM INTO periódico (cron), como o hub de memória.

## 9. Compatibilidade e migração

- O workflow default (queue→work→review→done), workspaces, deps, gates seguem idênticos.
- Clientes antigos (MCP local) → repontados para o 2º MCP (`task-orch-vps`).
- Migração seletiva do banco atual → ver `docs/migration-analysis.md`. Banco da VPS
  **nasce zerado**; só o útil entra.

## 10. O que explicitamente NÃO está nesta arquitetura v0.1

UI web, eventos externos, flow DAG editável, multi-tenant, híbrido. Todos no PRD §6
(futuro). Esta ARCH cobre só a **fundação**: serviço central unificado + segurança +
presença/claims + agent_id.

## 11. Impactos arquiteturais do painel de 13 papéis (14/out)

Fonte: `conhecimentos-de-ia/pesquisa/orc-painel-papeis-2026-10-14/SINTESE.md`. O painel
muda a arquitetura em pontos concretos — registrados aqui como requisitos técnicos.

### 11.1 Gate como predicado tipado e bloqueante (não nota frouxa)
Hoje o note-gate do task-orch é opcional e `complete` o pula. Novo modelo:
- Gate = **schema de predicados tipados** por workspace/papel: ex.
  `{ci: green, coverage: ≥0.80, scenarios: ≥N, approved_by: role=qa}`.
- `advance`/`complete` **falham fechado** se predicados não satisfeitos — sem bypass
  silencioso. Bypass só com flag auditada (`hotfix`, `break-glass`), registrada.
- Veredito do gate é **estruturado** (`{verdict, failed_predicates[], defect_item_id}`),
  legível por agente-revisor.

### 11.2 Projeção por papel (mesma verdade, duas views)
O dado é um só (schema struct). Views são **projeções**, não cópias:
- `view=struct` (MCP, agentes): enum, campos tipados, `next_action` como verbo.
- `view=narrativa` (UI/humano): rollup, 1-linha por épico, previsão em linguagem de negócio.
- `view=negocio` (cliente não-TI): sem jargão, previsão faixa+confiança, custo R$.
Implementação: camada de projeção sobre o modelo, resolvida por `role`/`view` na requisição.

### 11.3 Tipos de trabalho (polimorfismo de fluxo)
`work_item.type ∈ {feature, bug, spike, debt, incident, operation}`. O **fluxo e os gates
dependem do type**:
- `feature` → fluxo+gates completos.
- `incident` → fluxo próprio (detect→mitigate→resolve→postmortem), severidade, timeline
  append-only, on-call; gate assíncrono pós-fato.
- `spike` → sem done-criteria, timebox, estado "sem-estimativa-por-design".
- `operation` → movido por evento não-git (deploy/scale/rollback).
Não forçar `queue→work→review→done` em todos.

### 11.4 Primitivas de concorrência de agente (no claims.py)
- Claim com **lease/TTL** — expira se o agente morre (heartbeat parou). Evita item travado.
- **Idempotency-key** por transição + **optimistic concurrency** (version/etag no item):
  retry seguro, sem efeito duplicado.
- **Backpressure**: resposta sinaliza WIP cheio → agente para de puxar.

### 11.5 Ingestão de eventos (núcleo, não futuro)
Receptor de webhook idempotente (dedup por delivery-id) + HMAC. Fontes: git (push/PR/merge),
CI (build/deploy), e eventos não-git (ops). Evento → transição de item. Fila **durável**
(não perde webhook em restart) — ver §11.7.

### 11.6 Observabilidade separada humano vs agente
Métricas particionadas por tipo de ator desde o schema. Entidades novas: `impediment`
(criar/atribuir/medir), `aging` (tempo parado por item). Dashboard não pode deixar
throughput de agente mascarar gargalo humano.

### 11.7 Resiliência do serviço central (meta — SPOF)
O serviço central é ponto único de falha e alvo. Requisitos: HA (quando viável),
backup/restore **testado** do estado, **fila de eventos durável** (webhooks não se perdem em
restart), modo degradado (se o Orc cai, CI/CD não para — o Orc **observa**, não está no
caminho crítico do deploy). Dogfooding: o Orc gere o próprio deploy e expõe seus SLOs.

### 11.8 Método de gestão como configuração
Núcleo = **Kanban/fluxo** (estados=colunas, claim=pull, WIP por ator). Scrum/SAFe = perfis
que adicionam timebox/cadência/PI por cima. XP = conjunto de gates + co-claim. O default
nunca é sprint. (Validado painel + curso IA 14/out: "ágil+Kanban é o futuro p/ IA".)
