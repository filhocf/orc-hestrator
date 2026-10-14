# PRD — Produto "X" (nome provisório: task-orch)

> **Merge de `task-orchestrator-py` + `mcp-session-registry`** num único produto: gestão
> de trabalho de um time humano+agentes, com coordenação de agentes nativa, servido de
> um ponto central.
>
> **Status:** v0.1 — fundação. **Data:** 2026-10-14. **Autor:** Claudio + Zero.
> **Base:** `docs/rfc/RFC-001-orquestracao-visual-colaborativa.md` (§13-§15) + decisões 14/out.
> **Nome:** provisório `task-orch`. Candidatos futuros: Condutor, Reger, FlowBoard.
> (Easter egg: "Orc" — o que carrega as tarefas nas costas 🪓.)

## 1. Problema

Hoje três dores somadas, provadas:

1. **Estado de trabalho não é confiável entre máquinas.** O task-orch usa SQLite local +
   sync de arquivo (OneDrive). Resultado medido 14/out: **109 itens com status divergente**
   entre sirdata e DNBSCDC289. O usuário (humano e agente) deixa de confiar no board.
2. **Coordenação de agentes é cega entre máquinas.** O session-registry sabe "quem está
   ativo" e "quem reivindicou o quê" — mas só **por-máquina**. Agentes em máquinas
   diferentes (ou a VPS) não se enxergam → retrabalho real (1h perdida implementando o
   que outra máquina já fazia).
3. **O estado depende da disciplina do operador.** Itens ficam `done` com push pendente,
   WIP infla porque ninguém fecha, trabalho feito direto numa máquina não vira item. A
   ferramenta exige que o humano/agente lembre de atualizar — e ele falha.

E uma dor de produto maior: **gestão de um time de N agentes + humano não tem um lugar
comum.** O humano não vê o que cada agente faz; os agentes não compartilham um plano.

## 2. Visão

**Um serviço central** onde N agentes (em qualquer máquina) e o humano **se conectam ao
mesmo estado de trabalho**: tarefas, arcos, dependências, gates — e **quem está fazendo o
quê, agora**. Agentes operam via MCP; o humano via UI. O estado é **fonte única**, não
cópias que divergem. Eventos externos (git, CI) movem itens **sem depender de alguém
lembrar**.

É o merge de dois produtos que sempre foram faces do mesmo: **o trabalho** (task-orch) e
**quem trabalha** (session-registry).

## 3. Personas

1. **Agente operador (Zero, T'Pol, Scotty, subagentes)** — 70% do uso. Consome MCP:
   pega próximo item, reivindica, avança, reporta, vê quem mais está ativo. **É o usuário
   primário.**
2. **Humano gestor (Claudio)** — 30% do uso. Via UI: vê o time, intervém em gates,
   dirige prioridade, reconcilia. Ponto de entrada visual, não operacional.
3. **Subagente efêmero** — recebe contexto de item/workspace, reivindica, executa, reporta.

## 4. Princípios de produto (o que norteia o escopo)

- **Backend-first (70/30).** A API que os agentes consomem vem antes da UI. Uma UI sobre
  backend que mente mostra mentira bonita. Ordem: estado confiável → automatismo por
  eventos → API MCP rica → UI.
- **Reduzir dependência da disciplina do operador.** O máximo de estado deve ser
  capturado por **evento** (git push, PR merge, gate passado movem o item), não por
  alguém lembrar de clicar. Automatismo > disciplina.
- **Fonte única de verdade.** Sem banco local que diverge (Etapa 1). Offline vem na
  Etapa 2 (híbrido), medido se dói.
- **Agente é ator de 1ª classe.** `agent_id` identifica quem faz o quê; presença e claim
  são do próprio item, não de um sistema separado.
- **Compatível com o que já roda.** O workflow atual (queue→work→review→done), workspaces,
  deps, gates, memory bridge continuam funcionando. Evolução, não ruptura.

## 5. Escopo v0.1 (fundação — o que entra)

Herdado e unificado dos dois produtos existentes:

### 5.1 Gestão de trabalho (de task-orchestrator-py)
- Work items hierárquicos (epic→feature→task→subtask), status, prioridade, complexidade,
  tags, due_at, metadata.
- Dependências (grafo, cycle detection, unblock_at).
- Notes por fase + **gates** (não avança sem a nota exigida).
- Workspaces (tag mapping, memory_tags, repos, conventions).
- Métricas, graph analytics, export/import, scheduling.

### 5.2 Coordenação de agentes (de mcp-session-registry, INCORPORADO)
- **Presença**: agente registra sessão, declara tema, heartbeat, reaping de stale.
- **Claim unificado**: reivindicar um **work item** OU um **recurso avulso** (arquivo,
  branch) — não perde o caso original do session-registry.
- **Conflito**: ver quem já está no item/recurso antes de pegar.
- **"Quem está no quê, agora"** como propriedade consultável do estado (não sistema à parte).

### 5.3 Infraestrutura (novo — o déficit real)
- **Serviço central na VPS** (fonte única). As máquinas apontam para lá via MCP
  StreamableHTTP. Sem banco local (Etapa 1).
- **Segurança**: nginx (basic auth na borda) + OAuth2 no serviço — padrão provado no hub
  de memória.
- **`agent_id` por requisição** (header/`_meta` per-request, precedência resolvida como no
  memory-service RFC #1285) — distingue N agentes atrás do mesmo socket.

## 6. Escopo futuro (NÃO v0.1 — registrado para não perder)

- **Eventos externos** movendo itens (git push, CI, ServiceNow) — alta prioridade pós-v0.1
  (é o automatismo que tira peso da disciplina — princípio §4).
- **UI de gestão** (board + graph view + timeline, WebSocket tempo real) — a parte "30%".
- **Flow DAG editável + actor-per-node** (o diferencial do RFC §3/§7).
- **Híbrido** (Etapa 2): primary local + secondary hub, offline-capable.
- **Multi-tenant / corporativo** (instância DTP: orgs, RBAC, SSO Keycloak) — RFC §14.
- **Claim com lease temporizado** (ideia roubada de task-ledger/llm-bus).

## 7. Fora de escopo

- Multi-user/auth corporativo (fica para a instância corporativa, não a individual v0.1).
- Execução de agentes (não é orquestrador de runtime como agent-fleet-o; é gestor de
  trabalho + coordenação. Agentes rodam onde já rodam).
- Substituir memory-service (são complementares: memória guarda fatos; task-orch guarda
  estrutura de trabalho + presença).

## 8. Critérios de aceite (v0.1)

- Serviço `task-orch` roda na VPS, exposto com nginx+OAuth2, banco **zerado**.
- Um 2º MCP (ex. `task-orch-vps`) conecta as máquinas ao serviço central.
- Agente consegue: criar/avançar item, reivindicar item/recurso, ver presença de outros
  agentes — **tudo contra o serviço central** (zero banco local).
- **Os 109 divergentes deixam de existir** (há uma fonte única; não há o que divergir).
- Migração seletiva: só o trabalho **útil** (arcos ativos, itens vivos) entra; o lixo fica
  para trás.
- `agent_id` distingue autor nas operações.

## 9. Métricas de sucesso (como sei que ajuda — resposta do CLIENT)

- **Confiança**: o board nunca mais mostra estado divergente (0 divergências estruturais).
- **Menos fricção de manutenção**: tempo gasto por sessão reconciliando/arrumando WIP → ~0.
- **Zero retrabalho cross-máquina**: presença central evita 2 agentes no mesmo item.
- **(pós-eventos)**: % de transições de item disparadas por evento vs manual sobe — menos
  dependência da disciplina.

## 10. Marco inicial de implementação (sequência)

1. Subir `task-orch` como serviço na VPS, banco **zerado**, nginx+OAuth2.
2. 2º MCP (`task-orch-vps`) nas máquinas apontando pra lá.
3. **Migração seletiva** do banco atual (801 itens, muito lixo) → só o útil. Critério de
   "útil" na análise de migração (`docs/migration-analysis.md`).
4. Validar E2E: agente opera contra a VPS; presença funciona cross-máquina.
5. Aposentar os bancos locais (viram legado/backup).

Detalhe técnico: ARCH (`docs/ARCHITECTURE-X.md`) + ADRs (`docs/adr/`) + análise de
migração (`docs/migration-analysis.md`).

## 11. Achados do painel de 13 papéis (incorporado 14/out)

Experimento: 13 vozes independentes (6 humanas + 4 agentes de IA + modelos-de-gestão +
scrum-master + tech-lead) estressaram o produto. Fonte:
`conhecimentos-de-ia/pesquisa/orc-painel-papeis-2026-10-14/` (BRIEFING + 13 vozes + SÍNTESE).
**Validação externa (curso IA, 14/out):** "ágil + Kanban é o futuro da gestão para IA" —
bate com a conclusão independente do painel.

### 11.1 Princípio organizador do produto
**Humano manda nos GATES; agente opera ENTRE gates.** Fronteira de autoridade por estado.
Resolve a tensão recorrente (humano aprova devagar / agente quer throughput) sem subordinar
um ao outro.

### 11.2 Decisões de método de gestão (confirmadas painel + curso)
- **Kanban + ad-hoc = NATIVO.** Default do Orc é **board de fluxo contínuo por evento, com
  pull via claim e WIP por tipo de ator** — NÃO sprint. Agente = ator de pull de alto
  throughput, sem cadência semanal; Kanban é a física natural para humano+IA.
- **Scrum / SAFe = perfil CONFIGURÁVEL** (camada opcional: timebox, capacidade, PI,
  portfólio). Nunca obrigatório. Cadência humana negociada atrita com agente — o Orc revela
  o descompasso, não o força.
- **XP = gates + co-claim** (par humano+agente num item), ativável em qualquer perfil.

### 11.3 Ajustes de escopo que o painel força (sobe prioridade vs PRD §6)
1. **Estado-por-evento é NÚCLEO, não futuro** — pilar validado por humano E agente.
2. **Gate tipado, bloqueante, por papel, sem bypass** — QA humano e QA agente deram o mesmo
   veredito: gate frouxo + `complete` que pula = teatro. Reescrever o modelo de nota-gate.
3. **Mesma verdade, duas views** — struct (agente, via MCP) + narrativa/rollup (humano, UI)
   projetadas do mesmo dado. Não é a UI depois; é projeção desde o schema.
4. **Separar métrica humano vs agente** — atividade de agente mascara impedimento humano
   (achado mais perigoso). "Impedimento" e "aging" como entidades; saúde ≠ throughput.
5. **Tipos de trabalho além de feature:** **incidente** (fluxo próprio detect→mitigate→
   resolve→postmortem + severidade/timeline) e **spike** (sem done-criteria, timebox) como
   tipos nativos; **evento não-git** (deploy/ops) move itens.
6. **Camada de tradução por papel para o não-TI** — previsão com faixa+confiança, custo em
   R$/pessoa-dia, zero jargão. Senão o cliente de negócio é estruturalmente excluído.

### 11.4 Primitivas de agente de 1ª classe (só os agentes pediram)
Lease/TTL no claim (agente morre → claim expira), idempotency-key + optimistic concurrency
(version/etag), backpressure (servidor sinaliza WIP cheio), `agent_id` auditável (não se
passar por humano), **verificação delegável** (sub-agente auditor cujo veredito vira
evidência no gate), roteamento por capacidade (Python→Reg, Java→Torres).

### 11.5 Tensão de valores NÃO resolvida (decisão do Claudio)
O Orc **revela** o descompasso de ritmo ("agente faz 10x"), mas pode levar o gestor a cobrar
o humano no mesmo ritmo. O Orc deve **ativamente proteger** o humano dessa comparação
(normalizar unidades, separar lentes) ou só **expor o dado cru**? É escolha de valores do
produto, não técnica. Pendente.
