# RFC: Sistema "X" — Orquestração Visual Colaborativa Humano-IA

**Data**: 2026-06-25 · **Retomado**: 2026-10-14 (sirdata)
**Autor**: Claudio + Zero (ex-Kiro)
**Status**: DRAFT — competitiva atualizada (§11.6), decisões §12 fechadas, estender-vs-adotar §13, perfis de deployment §14, **decisão de arquitetura §15 (VPS fonte única → híbrido por etapas)**
**Antecedente**: `RFC-task-orchestrator-evolution.md` (histórico), este RFC o supersede como visão de produto
**Localização canônica**: `docs/rfc/RFC-001-orquestracao-visual-colaborativa.md` neste repo (movido do CdIA em 14/out — o task-orchestrator-py É o backend que evolui para este produto)
**Insumos**: `docs/rfc/matriz-decisao-oss-2026-10-14.md` (matriz requisitos×produtos OSS) · gatilho: 109 itens status-divergente sirdata↔DNBSCDC289 (sync union-only não reconcilia)

## 1. Problema

Hoje existem três mundos separados:

| Mundo | Ferramenta | Quem usa | Limitação |
|-------|-----------|----------|-----------|
| Gestão de tarefas | Kanboard, Jira, Linear | Humano | Sem inteligência, passivo |
| Orquestração IA | LangGraph, CrewAI, AutoGen | Agente | Caixa preta para o humano |
| Execução agêntica | task-orchestrator + MCP | Agente (humano via proxy) | Humano não interage direto |

O humano não vê o grafo de decisões do agente. O agente não respeita mudanças manuais do humano no board. São sistemas paralelos que não convergem.

## 2. Visão

Um sistema unificado onde:
- O **grafo de fluxo** é visível, editável, e compartilhado entre humano e agente
- **Tarefas** percorrem o grafo — ambos podem mover, criar, bloquear
- **Decisões** são nós no grafo — o humano pode entrar a qualquer momento
- **Eventos** (git, CI, deploy) movem tarefas automaticamente
- A **mesma interface** serve o humano (visual) e o agente (API/MCP)

## 3. Modelo Conceitual

```
Workspace (= projeto ou tema)
├── Flow (grafo de decisões — DAG editável)
│   ├── Node: "Triagem"        [actor: human]
│   ├── Node: "Análise"        [actor: agent | human]
│   ├── Node: "Implementação"  [actor: agent]
│   ├── Node: "Review"         [actor: human, gate: true]
│   ├── Node: "CI/CD"          [actor: event, trigger: push]
│   └── Node: "Done"           [terminal]
├── Items (tarefas concretas percorrendo o flow)
│   ├── Item A → está em "Implementação" (agent working)
│   ├── Item B → está em "Review" (aguardando humano)
│   └── Item C → está em "Triagem" (humano decide)
└── State (snapshot: quem está fazendo o quê agora)
```

### 3.1 Primitivas

| Primitiva | O que é | Quem cria/edita |
|-----------|---------|-----------------|
| **Workspace** | Container de trabalho (MIR, RER, pessoal) | Humano |
| **Flow** | Grafo DAG de nós (workflow) | Humano + Agente |
| **Node** | Etapa no flow (com actor, gate, triggers) | Humano |
| **Item** | Unidade de trabalho que percorre o flow | Humano + Agente |
| **Transition** | Aresta entre nós (condições opcionais) | Humano + Agente |
| **Event** | Trigger externo que move items (git, CI, timer) | Sistema |

### 3.2 Atores

| Actor | Pode fazer |
|-------|-----------|
| **human** | Criar items, mover entre nós, editar flow, aprovar gates |
| **agent** | Criar items, mover (respeitando gates), executar trabalho, sugerir |
| **event** | Mover items automaticamente (push→CI, merge→deploy) |
| **system** | Enforce WIP limits, detectar stale, auto-archive |

### 3.3 Gates

Um nó pode ter `gate: true` — significa que a transição para o próximo nó requer **aprovação explícita** do actor designado. O agente não pode pular gates humanos. O humano pode pular qualquer gate.

### 3.4 Interação no Grafo

O diferencial: **ambos veem e operam no mesmo grafo em tempo real**.

**Humano na UI:**
- Vê o flow como grafo visual (nós + arestas)
- Vê items como cards nos nós
- Drag-drop: move item entre nós
- Click no nó: edita actor, gate, triggers
- Insere nó novo no meio do flow (split edge)
- Remove nó (merge edges)
- Bulk: seleciona vários items → move/archive/cancel

**Agente via MCP:**
- `flow.get_state()` → snapshot do grafo + items
- `flow.advance(item, node)` → move item (respeitando gates)
- `flow.suggest_move(item, reason)` → sugere mas não move (gate humano)
- `flow.create_item(node, ...)` → cria item no nó correto
- `flow.watch(events)` → reage a transições

## 4. Diferenças vs Existentes

### vs Kanboard
- Kanboard: colunas fixas, sem inteligência, sem actor por etapa
- X: grafo editável, nós com actor/gate/trigger, agente participa

### vs LangGraph
- LangGraph: grafo definido em código, humano não vê nem edita, execução batch
- X: grafo visual editável, humano intervém a qualquer momento, execução contínua

### vs task-orchestrator-py (hoje)
- task-orch: status fixos (queue→work→review→done), humano opera via agente
- X: flow customizável por workspace, humano opera direto na UI

### vs Linear
- Linear: workflows por time (statuses), sem agente, sem grafo visual
- X: workflow é grafo DAG (não linear), agente é cidadão de primeira classe

## 5. Arquitetura Proposta

```
┌─────────────────────────────────────────────┐
│                  UI (React)                   │
│  Board kanban + Graph view + Timeline        │
│  WebSocket ↔ real-time state                 │
└────────────────────┬────────────────────────┘
                     │ HTTP + WS
┌────────────────────▼────────────────────────┐
│              Backend (Python)                 │
│  FastAPI + StreamableHTTP MCP                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Flow     │ │ Items    │ │ Events   │    │
│  │ Engine   │ │ Store    │ │ Bus      │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│         SQLite + WAL                         │
└────────────────────┬────────────────────────┘
                     │ MCP (StreamableHTTP)
┌────────────────────▼────────────────────────┐
│           Agentes (Kiro, CAO, etc)           │
│  Consomem MCP tools do backend              │
│  advance, create, suggest, watch            │
└─────────────────────────────────────────────┘
                     │ Webhooks
┌────────────────────▼────────────────────────┐
│         Eventos Externos                     │
│  Git push, Jenkins build, PR merge,         │
│  Timer (cron), ServiceNow CHG closed        │
└─────────────────────────────────────────────┘
```

### 5.1 Storage

SQLite (herança task-orchestrator-py):
- `flows` — definição do grafo (nós, arestas, actors, gates)
- `items` — work items com `current_node` em vez de `status`
- `transitions` — log de movimentações (quem, quando, de→para)
- `events` — triggers registrados (patterns → ações)
- `state_snapshots` — WAL-friendly snapshots para multi-machine sync

### 5.2 Transport

- **UI ↔ Backend**: HTTP REST + WebSocket (push de state changes)
- **Agente ↔ Backend**: MCP StreamableHTTP (já funciona hoje)
- **Eventos ↔ Backend**: Webhooks HTTP (Jenkins, GitHub, ServiceNow)

## 6. Migração do task-orchestrator-py

O "X" é a **evolução** do task-orchestrator, não substituição:

| task-orch hoje | X |
|----------------|---|
| `status` (queue/work/review/done) | `current_node` (nó no flow) |
| `advance_item(trigger)` | `flow.advance(item, target_node)` |
| Workspace | Workspace (mantém) |
| Dependencies | Transitions com condições |
| Notes por fase | Notes por nó |
| Execution stack | Actor stack (quem está atuando) |
| Tags | Tags (mantém) |
| Priority | Priority (mantém) |
| WIP alert | WIP limit por nó (enforce) |

### Compatibilidade

O flow default seria `queue → work → review → done` — exatamente o workflow atual. Workspaces existentes migram automaticamente para esse flow. Quem quiser customizar, edita o grafo.

## 7. Flows de Exemplo

### 7.1 Desenvolvimento MIR (feature)
```
Backlog → Análise[human] → Spec[agent] → Review Spec[human,gate] 
→ Implementação[agent] → Testes[agent] → Code Review[human,gate]
→ CI[event:push] → Deploy DEV[event:ci-green] → Validação[human]
→ Deploy PRD[human,gate] → Done
```

### 7.2 Bug fix (urgente)
```
Triagem[human] → Fix[agent] → Teste[agent] → Deploy[event:push] → Done
```

### 7.3 Pesquisa/Curadoria
```
Ideação[human] → Pesquisa[agent] → Análise[agent] → Revisão[human] → Publicação[human] → Done
```

### 7.4 Operacional (CHG/RITM)
```
Solicitação[human] → Abertura[agent] → Aguardando[event:sn-update] → Validação[human] → Done
```

## 8. MVP — O que implementar primeiro

### Fase 0: Fundação (2 semanas)
- Schema migration: `current_node` + `flows` table
- Flow default (queue→work→review→done) criado automaticamente
- API MCP compatível (advance_item continua funcionando, mapeia para flow.advance)
- UI: graph view (vis.js ou mermaid) ao lado do kanban existente

### Fase 1: Interação dual (2 semanas)
- WebSocket push de state changes
- UI: drag-drop item entre nós
- UI: criar/editar nós do flow
- MCP: flow.get_state, flow.advance, flow.suggest_move
- Gates: node com gate=true requer aprovação

### Fase 2: Eventos (1 semana)
- Webhook receiver (POST /events)
- Event patterns: `{source: "github", action: "push", branch: "main"}` → move items
- Jenkins integration (build result → advance)

### Fase 3: Multi-actor (1 semana)
- Actor visibility: "quem está atuando neste item agora"
- Conflict detection: humano e agente tentam mover o mesmo item
- Suggest mode: agente sugere, humano aprova (lightweight gate)

## 9. Nome?

Candidatos:
- **FlowBoard** — flow + board
- **OrchestraUI** — orquestração visual
- **DualFlow** — dual-actor flow
- **HarmonAI** — harmonia humano-IA
- **Condutor** — quem conduz a orquestra (PT-BR)
- **Reger** — reger = conduzir (PT-BR, mais conciso)

## 10. Relação com produtos existentes

- **task-orchestrator-py**: evolui para ser o backend do X
- **task-orchestrator UI** (8745): evolui para ser a UI do X
- **Kiro CLI**: continua consumindo via MCP (transparente)
- **Kanboard**: referência de UX (Claudio foi colaborador), não dependência
- **LangGraph**: conceito de grafo de estado, mas X é visual e editável

## 11. Pesquisa Competitiva (25/jun/2026)

### 11.1 Cline Kanban (cline.bot)
- **Status**: Research preview (experimental)
- **O que faz**: Board kanban onde cada card é um agente CLI rodando em git worktree isolado. Multi-agent (Cline, Claude Code, Codex).
- **Humano**: cria cards, configura agentes, revisa diffs
- **Agente**: cria cards, link entre cards, auto-commit, auto-PR
- **Workflow**: fixo (backlog→doing→review→done)
- **Docs**: https://docs.cline.bot/usage/kanban, https://cline-kanban.mintlify.app/introduction
- **Gap vs X**: sem flow editável, sem gates, sem actor-per-node, só para código

### 11.2 Vibe Kanban (YC S25, BloopAI — vibe-kb.com)
- **Status**: Lançado, YC-backed, Rust backend, open source (github.com/BloopAI/vibe-kanban)
- **O que faz**: Board para planning + review de coding agents. Multi-agent (Claude Code, Cursor, Copilot, Gemini CLI). Git worktrees isolados. Code review built-in. MCP integration.
- **Humano**: planeja issues, revisa código, gerencia board
- **Agente**: executa tasks em worktrees, produz código
- **Workflow**: fixo (plan→agent working→review→done)
- **Docs**: https://vibekanban.com/docs
- **Gap vs X**: sem DAG customizável, sem actor dinâmico, foco exclusivo em código

### 11.3 Hermes Kanban (Nous Research — hermes-agent)
- **Status**: Lançado, open source (github.com/Agent-3-7/hermes-agent-mission-control)
- **O que faz**: Board compartilhado entre múltiplos agentes Hermes. Dispatcher atribui tasks, agents operam via toolset dedicado (kanban_show, kanban_complete, kanban_block, kanban_heartbeat, kanban_comment, kanban_create, kanban_link, kanban_unblock). Persiste entre restarts. Human-in-the-loop via dashboard.
- **Humano**: vê dashboard, intervém, cria tasks manualmente
- **Agente**: claim, comment, complete, block, heartbeat, create, link
- **Dependencies**: sim (kanban_link)
- **Workflow**: board kanban padrão (não DAG)
- **Docs**: https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
- **Gap vs X**: sem flow visual editável, sem auto-move por eventos externos, sem actor-per-node, sem grafo

### 11.4 Posicionamento comparativo

| Feature | Cline Kanban | Vibe Kanban | Hermes Kanban | **X** |
|---------|-------------|-------------|---------------|-------|
| Board visual | ✅ | ✅ | ✅ | ✅ |
| Multi-agent | ✅ | ✅ | ✅ | ✅ |
| Human interacts | ✅ (review) | ✅ (plan+review) | ✅ (dashboard) | ✅ (full) |
| Workflow customizável | ❌ fixo | ❌ fixo | ❌ fixo | ✅ DAG editável |
| Actor per node | ❌ | ❌ | ❌ (dispatcher) | ✅ human/agent/event |
| Gates (human approval) | ❌ | ✅ (review step) | ❌ | ✅ per-node |
| Auto-move por eventos | Parcial (auto-PR) | ❌ | ❌ | ✅ webhooks |
| Dependencies | ❌ | ❌ | ✅ (links) | ✅ |
| Flow visual (grafo) | ❌ | ❌ | ❌ | ✅ **diferencial** |
| MCP native | ❌ | ✅ | ❌ (toolset custom) | ✅ |
| Agnóstico (não só código) | ❌ | ❌ | ✅ | ✅ |
| Open source | Research | ✅ | ✅ | ✅ |

### 11.5 Diferencial confirmado

Nenhum produto existente oferece:
1. **Flow como DAG editável visualmente** — todos usam board kanban com colunas fixas
2. **Actor per node** — nenhum define quem atua em cada etapa (human/agent/event)
3. **Eventos externos** — nenhum reage a Jenkins/GitHub/ServiceNow para auto-move
4. **Agnóstico + grafo** — Hermes é agnóstico mas sem grafo; Cline/Vibe têm visual mas só código

O espaço de "orquestração visual colaborativa com grafo editável" está **aberto**.

### 11.6 Addendum competitivo — out/2026 (pesquisa web direta, 14/out)

Reavaliação 4 meses depois. **A categoria explodiu** — dezenas de projetos novos. O
"espaço aberto" de junho ficou povoado, MAS quase tudo é **coding-fleet coordination**
(N agentes editando o MESMO repo: claim de arquivo, worktree isolado, PR gate), com
**workflow fixo**. O diferencial do X (flow DAG editável + actor-per-node + eventos
externos + agnóstico a código) **continua raro**.

Novos entrantes mapeados:

| Projeto | Perfil | Cobre o diferencial do X? |
|---------|--------|---------------------------|
| **agent-board** (vineetkukreti) | "Jira/Linear p/ agentes": custo, bloqueio, auto-registro, docker-compose, backend+frontend+mcp | Mais perto do "gestão do time", mas workflow fixo, sem DAG/actor-per-node. Imaturo (0★). |
| **agent-fleet-o** (escapeboy) | mission control: **DAG visual** + human-in-the-loop + MCP + audit | O único com DAG visual. Mas foco em orquestrar EXECUÇÃO (rodar agentes), não gerir backlog/arcos. |
| **wood-fired-tasks** | TS/Fastify, SQLite+MCP+REST+CLI+**SSE**, claim atômico, auto-unblock/auto-complete | Tecnicamente o mais próximo do task-orch. Workflow fixo, coding-fleet. |
| **orchy** (aboglioli) | Rust, 71 MCP tools, task board + knowledge + graph edges. **Vault markdown, SEM servidor** | Superset conceitual (task+memória juntos) MAS "sem servidor" = mesmo problema de sync que temos. |
| **llm-bus** | AGPL, claims+leases+ledger+presence+handoffs+task graph, Streamable HTTP | Coordenação madura. Workflow fixo. |
| **veritas-kanban** (BradGroux) | board + camadas opcionais (MCP, governance **gates**, squad chat) | Modelo em camadas ~ nossos gates. Sem DAG. |
| **helix** (helixml) | fleet privado spec-coding, 1 desktop GPU/agente, kanban + PR gate | Pesado (GPU). Overkill. |
| **Agent-Kanban**, **AgentRQ**, **synapse-channel**, **task-ledger**, **mcp-coordinator** | variações de board+claim+presença | Nenhum com DAG editável. task-ledger tem **claim com lease temporizado** (bom padrão). |

**Veredito atualizado:** o diferencial de junho (§11.5) resiste — nenhum oferece
**flow DAG editável + actor-per-node + eventos externos + agnóstico**. agent-fleet-o
chegou perto (DAG visual) mas é orquestrador de execução, não gestor de arcos. O X
continua um espaço válido. O que mudou: há mais **peças para roubar** (SSE em tempo
real, claim com lease, custo-por-agente, auto-registro).

## 12. Decisões em aberto

| # | Decisão | Status (14/out) |
|---|---------|-----------------|
| 1 | Nome definitivo | **ABERTO** — candidatos §9 (Condutor/Reger favoritos PT-BR). Escolher antes do repo. |
| 2 | Grafo engine (SQLite puro vs networkx/rustworkx) | **ABERTO** — decidir no Fase 0. SQLite puro provável (continuidade). |
| 3 | UI framework (React vs Svelte) | **ABERTO** — React (há UI 8745 do task-orch como base). |
| 4 | Repo: evoluir task-orch vs novo | **RESOLVIDO (14/out): evoluir o task-orchestrator-py.** Ver §13 — temos 4/5 peças provadas, zero migração, blueprint de hub central já existe. |
| 5 | Produto aberto? | **ABERTO** — provável open-source (linha -one / harness), decidir depois do MVP interno. |
| 6 | Linguagem backend (Python vs Rust) | **RESOLVIDO (14/out): Python** — continuidade do task-orch (Python 3.11+), reaproveita engine/schema/MCP existentes. Rust só se performance exigir (não é o caso em single-user). |

## 13. Decisão estender-vs-adotar + próximos passos (14/out/2026)

**Contexto da retomada:** 109 itens com status divergente entre sirdata e DNBSCDC289
provaram, com número, que o sync union-only (SQLite+OneDrive, "fora de escopo" no PRD
do task-orch) não sustenta multi-máquina. O Claudio pediu: "um lugar comum onde N
agentes se conectam, veem o mesmo backlog de tarefas/arcos, e eu gerencio o time" —
que é **exatamente a visão deste RFC** (concebido em jun, parado em DRAFT).

**Decisão: ESTENDER o nosso stack, não adotar pronto.** Justificativa medida:

- **4 das 5 peças já existem e provadas:**
  - Modelo (task-orch): itens, arcos, deps, gates por nota, workspaces, graph-metrics, export. ✅
  - Coordenação de agente (session-registry): presença, claim, heartbeat, conflito, reaping. ✅ (mas por-máquina → tornar central)
  - Blueprint hub central (memory-service): N clientes → 1 serviço VPS + delta-sync + `agent_id` header per-request. ✅ **provado em produção** (mesmo padrão).
  - Hub (VPS cfnarede.dev). ✅
  - UI de gestão: ❌ é o que falta construir (F018 planejado) — mas já estava no roadmap.
- **Os prontos (§11.6) não cobrem** flow DAG + actor-per-node + gates por nota + ponte com memory-service, e são imaturos (0-2★, 1 autor). Migrar 801 itens + 223 deps + 205 notas + workspaces por uma ferramenta coding-fleet de workflow fixo seria regressão.
- Somos autores do task-orch → controlamos a evolução.

**O déficit real (o que de fato falta construir):**
1. **Backend compartilhado** — task-orch servindo da VPS (não SQLite+OneDrive). Aplicar o padrão do hub de memória (delta-sync de transições OU serviço central único).
2. **session-registry central** — presença/claim cross-machine (não por-máquina).
3. **`agent_id` como ator de 1ª classe** no task-orch (precedência header per-request, já resolvida no memory-service RFC #1285 — reusar).
4. **UI de gestão** (Fase 0-1 deste RFC): graph view + kanban + WebSocket tempo real.

**Peças a roubar dos prontos (independe da decisão):**
- claim com **lease temporizado** (task-ledger/llm-bus) — melhor que o advisory lock atual do session-registry.
- **SSE/WebSocket tempo real** (wood-fired-tasks) — já previsto no §5.2 deste RFC.
- **custo-por-agente** + **auto-registro via tool call** (agent-board).
- **camadas opcionais** board→MCP→gates (veritas-kanban) — alinha com o MVP faseado §8.

**Experimento barato antes de comprometer (opção, decisão do Claudio):** subir
agent-board (docker-compose) e ver com dado se o modelo cobre arcos/gates ou é só
coding-fleet. Se a hipótese "estender vale mais" já está forte, pode pular direto ao
Fase 0.

**Próximos passos propostos:**
1. Escolher nome (decisão #1) — desbloqueia repo/branding.
2. Fase 0 do §8 sobre o task-orchestrator-py: schema `flows` + `current_node`, flow
   default compatível (queue→work→review→done), backend central na VPS (resolve o sync
   que gerou os 109 divergentes).
3. Reconciliar os 109 divergentes atuais (decisão pendente A/B/C — ver sessão 14/out).
4. UI graph view (Fase 1).

## 14. Dois perfis de deployment (individual / corporativo) — visão de produto

Expansão de visão (Claudio, 14/out): o mesmo núcleo serve dois mercados. Mesma
arquitetura, não bifurca o código — o corporativo é camada adicional sobre o núcleo.

| | **Individual** (dev solo + seus agentes) | **Corporativo** (gestor + N devs + N agentes) |
|---|---|---|
| Quem gerencia | o próprio dev | gestor + time |
| Escopo | projetos pessoais | portfólio/esteira da empresa |
| Multi-tenant | não (1 usuário) | **sim** (orgs/times/projetos/RBAC) |
| Auth | OAuth2 local | **SSO corporativo** (DTP: Keycloak/gov.br) |
| Integração | git pessoal, MCPs locais | **linha de dev**: GitLab, Jenkins, ServiceNow, esteira |
| Deploy | VPS pessoal (cfnarede.dev) | cluster corporativo (HCSO) |

**Gancho DAIA / linha de dev:** os `Event`s externos do §3.1 (git push, CI, ServiceNow
CHG) movendo items são o que pluga o board na esteira da empresa — devs + agentes no
mesmo flow visível ao gestor. Posicionável como oferta DAIA (instância corporativa de
orquestração humano-IA).

**Sequenciamento (recomendação, decisão do Claudio):** construir o **núcleo individual
primeiro** (resolve o problema real + é OSS linha -one), com o **schema já desenhado
para não travar o corporativo** (prever `tenant`/`org` cedo; `agent_id` e `workspace` já
previstos). Corporativo/DAIA = camada que se liga depois, não escopo de implementação
agora.

**Nota de evolução de método (Claudio, 14/out):** "naquele tempo [jun] tu era bem mais
complicado; hoje te vejo trabalhando bem melhor". O produto é, em parte, a
institucionalização do que fez o agente trabalhar melhor — flow explícito, actor por
etapa, gates humanos, estado compartilhado. É argumento de posicionamento, não só técnico.

## 15. Decisão de arquitetura — serviço central na VPS, híbrido por etapas (14/out)

**Decisão do Claudio (14/out), confirmada:** parar com "banco local + sync" (causa-raiz
dos 109 divergentes) e ir para **serviço central na VPS, todos consumindo de lá**.
Trocar o problema difícil (consistência distribuída) pelo fácil (cliente-servidor).

### 15.1 Distinção que fundamenta a decisão
- **Delta-sync** (memory-service) = banco LOCAL em cada máquina + event-log reconcilia.
  Resolve "N cópias convergem". Funciona offline.
- **Serviço central** = SEM banco local; todos leem/escrevem o MESMO banco na VPS.
  Resolve "1 fonte de verdade". Depende de rede.
- São **alternativas, não complementares.** Com fonte única não há o que sincronizar →
  **não se constrói delta-sync para o task-orch** (seria resolver problema que a fonte
  única já elimina).

### 15.2 Plano por ETAPAS (decidido)
- **Etapa 1 — Fonte única na VPS (AGORA).** task-orchestrator roda como serviço na
  cfnarede.dev; as 3 máquinas apontam para lá via MCP StreamableHTTP (deixam de ter
  banco local). Mata os 109 divergentes imediatamente. Mais simples. Trade-off aceito
  conscientemente: **sem rede/VPS = board indisponível** (hoje, com banco local, há board
  offline). Cobre ~95% do uso real.
- **Etapa 2 — Híbrido (DEPOIS, quando a Etapa 1 estiver de pé).** Primary local +
  secondary HTTP (hub), modelo do memory-service — funciona offline e sincroniza quando
  online. É o melhor dos dois mundos; só construir após provar a Etapa 1 e **se** a
  indisponibilidade offline incomodar na prática (medir antes de pagar o custo).

### 15.3 Segurança (padrão provado no memory-service)
- **nginx (basic auth na borda) + OAuth2 no serviço.** Mesma receita validada no hub de
  memória (`cfnarede.dev/memory`, serviço em `127.0.0.1`, nginx reverse proxy).
- Instância corporativa futura: OAuth2 → SSO DTP (Keycloak). Fora do escopo da Etapa 1.

### 15.4 Migração do estado atual (a resolver antes de erguer)
- 801 itens + 223 deps + 205 notas existem; **109 com status divergente** entre sirdata
  e DNBSCDC289. O banco da VPS precisa de um estado inicial reconciliado.
- Pendente decisão: (a) reconciliar os 109 (A/B/C da sessão 14/out) e importar o
  resultado; OU (b) partir do estado de UMA máquina (ex. DNBSCDC289, que fez limpeza
  RER/Roma) como baseline e descartar a divergência. **Decidir antes do import.**

### 15.5 Sobre os OSS (não adotar, aprender)
Stack PHP/Laravel (agent-fleet-o) descartada por preferência do Claudio. Mas **trazer
ideias**: DAG visual + actor-per-node + human-in-the-loop (agent-fleet-o); UI React/TS +
camadas board→MCP→governance (veritas-kanban, MIT, dá p/ ler código direto); claim com
lease temporizado (task-ledger/llm-bus); SSE tempo real (wood-fired-tasks). Reimplementar
em Python/TS no nosso núcleo.

### 15.6 Próximo passo imediato
Erguer o task-orchestrator como serviço na VPS (Etapa 1) — vps-deploy + nginx+OAuth2.
Antes: decidir a migração §15.4. Evolução das feats (UI, DAG, gates, agent_id ator)
acontece JÁ no serviço central, não mais no banco local.
