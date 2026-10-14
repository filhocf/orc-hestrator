# Matriz de decisão — plano de controle de time de agentes (14/out/2026)

> Método pedido pelo Claudio: montar matriz dos requisitos descritos × produtos OSS,
> pontuar, e daí ver o que vale experimentar. Alimenta a decisão §13 do
> `RFC-sistema-X-orquestracao-colaborativa.md`. Pesquisa web direta.

## 1. Requisitos (o que o Claudio descreveu) + pesos

Derivados da conversa de 14/out (não do viés do Zero). Peso: **3=essencial, 2=importante, 1=desejável**.

| # | Requisito | Peso | Origem (fala do Claudio) |
|---|-----------|------|--------------------------|
| R1 | **Backend central** — N clientes conectam a 1 fonte de verdade (resolve os 109 divergentes) | 3 | "lugar comum", "problemas sérios de sync" |
| R2 | **N agentes como atores** — presença, claim de item, quem faz o quê | 3 | "N agentes conectam e entendem o processo" |
| R3 | **Conexão via MCP** — agentes operam por MCP | 3 | "os 2" (MCP + UI) |
| R4 | **UI web de gestão** — board/painel p/ o humano ver e dirigir o time | 3 | "os 2", "eu tenha gestão do time" |
| R5 | **Tarefas/processos/ARCOS** — trabalho de longo prazo, hierárquico, não só ticket raso | 3 | "tarefas/processos/arcos" |
| R6 | **Gates** — aprovação humana explícita entre etapas | 2 | nosso dev-workflow G0-G6; RFC §3.3 |
| R7 | **Flow DAG editável + actor-per-node** — workflow custom, não colunas fixas | 2 | diferencial do RFC Sistema X |
| R8 | **Eventos externos** — git/CI/ServiceNow movem itens (esteira) | 2 | "integrar até com uma linha de dev" |
| R9 | **Multi-tenant / corporativo** — orgs/times/RBAC p/ instância da empresa | 2 | "instância corporativa p/ gerenciar a empresa" |
| R10 | **Agnóstico a código** — não só coding-fleet; qualquer tipo de trabalho | 2 | arcos de pesquisa/curadoria/infra, não só PR |
| R11 | **Integra memory-service + nossos gates** | 1 | ecossistema atual |
| R12 | **Maturidade/sustentação** — comunidade, não morre em 1 autor | 2 | risco de adotar/manter |
| R13 | **Dependências pré-existentes** — 801 itens, arcos, workspaces já no task-orch | 1 | custo de migração |

## 2. Scorecard (✅=atende, 🟡=parcial, ❌=não; score = Σ peso×valor, ✅=1 🟡=0.5 ❌=0)

| Req (peso) | **Nosso (task-orch + session-registry)** | veritas-kanban (840★ MIT) | agent-fleet-o (73★ AGPL) | agent-board (0★) | wood-fired-tasks (2★) | orchy (2★) | llm-bus |
|------------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| R1 backend central (3) | ❌ (sync arquivo) | ✅ server | ✅ Laravel | ✅ | ✅ SQLite+SSE | 🟡 vault/git | ✅ |
| R2 agentes atores (3) | ✅ (session-reg) | ✅ | ✅ | ✅ auto-reg | ✅ claim atômico | ✅ | ✅ |
| R3 MCP (3) | ✅ | ✅ | ✅ 670 tools | ✅ | ✅ | ✅ 71 tools | ✅ |
| R4 UI gestão (3) | ❌ (F018 planejado) | ✅ React | ✅ Livewire | ✅ front | 🟡 | ❌ (markdown) | ❌ |
| R5 arcos/longo prazo (3) | ✅ 4 níveis+deps | 🟡 kanban+scrum | 🟡 workflow exec | 🟡 tickets/sprints | 🟡 task+subtask | ✅ goal+subtask | 🟡 task graph |
| R6 gates (2) | ✅ nota-gate | 🟡 governance layer | ✅ HITL approval | ❌ | ❌ | ❌ | 🟡 |
| R7 DAG+actor-node (2) | ❌ (status fixo) | ❌ kanban | ✅ DAG visual | ❌ | ❌ | ❌ | 🟡 task graph |
| R8 eventos externos (2) | 🟡 scheduling | 🟡 webhooks | ✅ workflow автom | 🟡 hooks | ❌ | ❌ | ❌ |
| R9 multi-tenant (2) | ❌ single-user | 🟡 local-first | ✅ Laravel multi | 🟡 projects | ❌ | ❌ | 🟡 |
| R10 agnóstico (2) | ✅ | 🟡 (dev-tools) | ✅ workflow geral | 🟡 | ❌ coding | 🟡 coding | 🟡 |
| R11 memory+gates nossos (1) | ✅ nativo | ❌ | ❌ | ❌ | ❌ | 🟡 knowledge | ❌ |
| R12 maturidade (2) | 🟡 nosso/1 autor | ✅ 840★/100f | 🟡 73★/12f | ❌ 0★ | ❌ 2★ | ❌ 2★ | ❌ |
| R13 sem migração (1) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Score ponderado (máx possível = 29)

| Produto | Score | % | Leitura |
|---------|------:|--:|---------|
| **Nosso (task-orch+session-reg)** | **21.0** | 72% | Core forte (arcos/gates/MCP/memory/agnóstico), buraco em **backend central + UI + DAG + multi-tenant** |
| **agent-fleet-o** | **20.5** | 71% | Único com DAG+HITL+multi-tenant+eventos. Buraco em arcos (é exec/workflow) e memory/gates nossos. PHP/Laravel. AGPL. |
| **veritas-kanban** | **18.0** | 62% | Mais maduro (840★). Buraco em DAG/actor-node, arcos profundos, gates fortes. React/TS (stack boa p/ nós). |
| **agent-board** | **13.0** | 45% | "Gestão do time" (custo/bloqueio) mas raso e imaturo. |
| **wood-fired-tasks** | **12.5** | 43% | Técnico sólido (SSE/claim atômico) mas coding-fleet, workflow fixo, imaturo. |
| **llm-bus** | **12.0** | 41% | Coordenação madura, sem UI, sem arcos. |
| **orchy** | **11.5** | 40% | Markdown vault = mesmo problema de sync, sem UI. |

## 3. Leitura da matriz (o que os números dizem)

1. **Empate técnico no topo: nosso (21) vs agent-fleet-o (20.5).** Os dois lideram por motivos OPOSTOS:
   - **Nosso** ganha em *core de trabalho* (arcos, gates por nota, agnóstico, memory bridge, zero migração) e perde em *infraestrutura* (backend central, UI, DAG, multi-tenant).
   - **agent-fleet-o** ganha em *infraestrutura* (DAG visual, HITL, multi-tenant Laravel, eventos, 670 MCP tools, 73★) e perde em *core* (é orquestrador de EXECUÇÃO de workflow, não gestor de arcos de longo prazo; não integra nosso ecossistema).

2. **Ninguém atende R5 (arcos) + R7 (DAG) + R9 (multi-tenant) ao mesmo tempo.** Essa tripla é exatamente o que o RFC Sistema X propõe e o mercado ainda não entregou junto.

3. **O gap do nosso é 100% INFRAESTRUTURA conhecida** (R1 backend, R4 UI, R7 DAG, R9 multi-tenant) — não é core. E 3 desses 4 já têm blueprint provado no nosso ecossistema (hub de memória = R1; F018 = R4; RFC §5 = R7).

## 4. O que vale experimentar (e por quê)

Dois experimentos baratos, com perguntas de falseamento claras:

### Exp-1 — **agent-fleet-o** (prioritário)
- **Por quê:** é o único que empata com o nosso e tem o que mais nos falta (DAG+HITL+multi-tenant+eventos). Se cobrir arcos de longo prazo, muda a decisão.
- **Pergunta de falseamento:** *consigo modelar UM arco real nosso (ex: síntese de belief, com G0-G5 e sub-itens) como um fluxo com gates humanos e estado persistente de longo prazo — ou ele força tudo num pipeline de execução efêmero?*
- **Custo:** docker, ~meio dia. Risco: AGPL (copyleft forte — relevante se virar produto) + stack PHP/Laravel (fora do nosso Python/TS).

### Exp-2 — **veritas-kanban** (secundário)
- **Por quê:** o mais maduro (840★, MIT, React/TS — stack que dominamos), modelo em camadas (board→MCP→governance) parecido com nosso gate.
- **Pergunta de falseamento:** *o "governance gate" dele equivale aos nossos note-gates? O board representa arcos hierárquicos ou só cards rasos? A camada MCP deixa N agentes operarem o mesmo estado?*
- **Custo:** ~2h. Risco baixo (MIT, stack nossa).

**NÃO experimentar agora:** agent-board/wood-fired-tasks/orchy/llm-bus — score baixo + imaturos + coding-fleet. Já descartados pela matriz.

## 5. Hipótese a confirmar/refutar com os experimentos

> O gap do nosso stack é **infraestrutura conhecida com blueprint provado**, enquanto o
> gap dos prontos é **core (arcos+gates+ecossistema) que teríamos de reconstruir neles**.
> Se os experimentos confirmarem que agent-fleet-o/veritas achatam arcos em pipeline/cards
> rasos → **estender** vence por larga margem. Se algum representar arcos+gates
> nativamente com maturidade → reabrir a decisão de adotar (provável: roubar a UI/DAG
> deles e manter nosso core).

Decisão final é do Claudio, após os experimentos.
