# Delta task-orch → Orc — evoluir ou recomeçar? (14/out/2026)

> Avaliação medida (não achismo) para decidir: o Orc nasce EVOLUINDO o task-orchestrator-py
> ou RECOMEÇANDO do zero? **Base:** código real + PRD-X/ARCH-X + painel de 13 papéis.

## 1. O que o task-orch JÁ tem (medido)

| Módulo | LOC | É o quê | Reusável no Orc? |
|--------|----:|---------|------------------|
| `engine.py` | 1964 | state machine, deps (cycle detection), gates, queries, hierarquia | ✅ **core de valor** — o que nenhum OSS tinha |
| `server.py` | 788 | MCP server (**FastMCP, já streamable-http**), 22 tools | ✅ base; adaptar p/ agent_id per-request |
| `ui/app.py` | 540 | **FastAPI + Kanban UI** (Jinja2, uvicorn) | ✅ base da UI (déficit do PRD já começado!) |
| `engine`+`db`+`schemas`+`workspace`+`checkpoints`+`prompts` | ~2600 | lógica + schema + gates + workspace | ✅ |
| testes | 1595 | 10 arquivos | ✅ rede de segurança |
| **total src** | **~3933** | — | — |
| session-registry (a incorporar) | 356 | presença + claim + db | ✅ pequeno, trivial de fundir |

**Fatos que mudam a decisão:**
- O transport **já é streamable-http** (não só stdio) — `MCP_TRANSPORT=streamable-http` + uvicorn. Metade da "infra VPS" já existe.
- **Já existe FastAPI + Kanban UI** — a UI (déficit do PRD §6) tem base pronta, não é do zero.
- `engine.py` é o core que o painel validou (gates, deps, hierarquia, workspaces) e que o mercado OSS não oferecia.

## 2. O que falta para virar Orc (o delta real)

Mapeado do PRD-X §11 + ARCH-X §11 contra o código atual:

| Gap | Tipo de mudança | Tamanho |
|-----|-----------------|---------|
| Backend central na VPS (deploy, não local) | **infra/config** (vps-deploy + nginx+OAuth2) | pequeno — padrão do memory hub |
| Incorporar session-registry (presence.py + claims.py) | **adição** (356 LOC a portar + unificar claim item\|resource) | pequeno |
| `agent_id` per-request (header) | **adição** no server/auth | pequeno (padrão RFC #1285 pronto) |
| Gate tipado bloqueante (hoje nota-gate frouxa + `complete` pula) | **refactor** do gate em engine.py/schemas.py | médio |
| Projeção por papel (struct/narrativa/negócio) | **adição** camada de view | médio |
| Polimorfismo de fluxo por `type` (incident/spike/op) | **extensão** da state machine | médio |
| Lease/TTL + idempotency + optimistic concurrency | **adição** em claims + transições | médio |
| Ingestão de eventos (webhook git/CI) | **adição** (receptor + fila durável) | médio-grande |
| Observabilidade humano vs agente | **adição** (métricas particionadas) | médio |

**Nenhum gap exige jogar fora o engine.** São adições e refactors incrementais sobre uma
base sólida. O item mais pesado (ingestão de eventos) é código novo que seria novo em
qualquer cenário — recomeçar não o deixaria mais fácil.

## 3. Avaliação: EVOLUIR vs RECOMEÇAR

### Argumentos a favor de RECOMEÇAR (honestos)
- Nome/branding novo, schema desenhado do zero para multi-tenant desde o início.
- Sem dívida de decisões antigas (status fixo, nota-gate frouxo).
- Oportunidade de escolher stack (ex: o painel elogiou struct-first).

### Argumentos a favor de EVOLUIR (mais fortes, medidos)
- **~3933 LOC de core + 1595 de teste já existem e funcionam.** `engine.py` é exatamente o
  diferencial que o mercado OSS não tinha (gates/deps/hierarquia/workspaces). Recomeçar =
  reescrever meses de lógica testada por ganho estético.
- **A infra que o Orc precisa já começou:** streamable-http ✅, FastAPI+Kanban UI ✅. Os 2
  maiores déficits do PRD têm base pronta.
- **Os gaps são adições/refactors incrementais, não reescrita.** Dá para fazer por fases,
  com os testes existentes de rede.
- **Migração de dados trivial:** mesmo schema de origem → o export/import seletivo já é
  previsto. Recomeçar com schema novo tornaria a migração MAIS difícil.
- **Risco menor:** evoluir com testes verdes a cada passo > big-bang de reescrita que
  historicamente estoura prazo e perde features sutis.
- Multi-tenant "desde o schema" (único ganho real do recomeço) pode ser **migration aditiva**
  (adicionar `tenant`/`org` nullable) — não exige começar do zero.

### Veredito
**EVOLUIR.** O task-orch não é um protótipo a descartar — é 70% do Orc já construído e
testado, com a infra (http+UI) começada. Recomeçar jogaria fora o core de valor por ganhos
que uma branch de evolução captura incrementalmente. O recomeço só se justificaria se o
engine fosse podre/inflexível — e não é (1964 LOC coesas, com testes).

## 4. Como evoluir (estratégia)

- **Branch `feat/orc`** (ou `feat/produto-x`) no task-orchestrator-py.
- **Fase 0:** serviço na VPS (já é http) + nginx+OAuth2 + agent_id. Banco zerado + migração
  seletiva (`migration-analysis.md`). → **mata os 109 divergentes.**
- **Fase 1:** incorporar session-registry (presence+claims unificado) + lease/idempotência.
- **Fase 2:** gate tipado bloqueante + polimorfismo de `type` (incident/spike).
- **Fase 3:** ingestão de eventos (webhook) + projeção por papel + observabilidade separada.
- **Fase 4:** UI evoluída (a base FastAPI/Kanban já existe) + multi-tenant (migration aditiva).
- Testes verdes a cada fase; a suíte de 1595 linhas é a rede.
- **Nome:** rebranding (task-orch → Orc/Condutor/Reger) é cosmético, pode vir a qualquer
  momento — não bloqueia e não exige repo novo.

## 5. O que NÃO fazer
- ❌ Repo novo do zero / reescrever o engine.
- ❌ Big-bang (reescrever tudo e migrar de uma vez).
- ❌ Esperar o nome definitivo para começar.

## 6. Validação independente (arch-analyst seven, Gate 0, 14/out)

Revisão independente com grafo indexado (`home-claudio-git-task-orchestrator-py` 794 nós +
`home-claudio-git-mcp-session-registry` 192 nós), anti-viés do autor. **Veredito: EVOLUIR**
— confirmado, mas com correções à minha avaliação:

**Confirmou com evidência própria:**
- `engine.py` = **61 funções procedurais** finas sobre SQLite (não God-module); acoplamento
  é ao `get_connection()`, não entre si. Extensível por adição.
- **Transição é DATA-DRIVEN** (`TRANSITIONS` dict, engine.py:77-89) → polimorfismo por type
  (incident/spike) = adicionar entradas no dict, **não reescrever**. (mais forte que eu avaliei)
- **Gate JÁ é tipado e bloqueante** (`check_gate` schemas.py:85-119 + `GATE_BLOCKED` em
  advance_item) — ~70% do pedido já existe. **Eu fui pessimista** ("nota-gate frouxa"); é
  evolução de schema, não troca de modelo.
- `server.py main()` já serve `streamable-http` stateless → pronto p/ nginx+OAuth2.
- session-registry: `SessionDB` mesmo idioma (sqlite3/WAL), tabelas **disjuntas** de
  work_items → merge sem conflito de schema.

**CORRIGIU a minha avaliação (eu subestimei):**
- **R1 — agent_id/multi-tenancy é o CALCANHAR, não "pequeno".** Todo o engine assume
  1 processo = 1 contexto (`get_connection()` global, sem coluna owner/tenant, tools sem
  identity per-request). Enfiar agent_id per-request toca TODA chamada de escrita + auth.
  "A parte que mais parece quase-recomeçar." → **reclassificar de 'pequeno' para OBRA
  ESTRUTURAL / fatia dedicada.** (minha tabela §2 estava otimista)
- **R2 — concorrência SQLite na VPS é risco PROVADO.** stateless_http serve central, mas o
  banco é arquivo local; N agentes concorrentes reabrem pegadinhas WAL/lock já em mistake
  notes. Precisa locking/serialização ou migração de backend. Risco operacional real.
- **R3 — engine.py monolítico sem camada de serviço** — cada feature engorda o mesmo
  arquivo. Não bloqueia, mas pede split (items/gates/deps/presence) para a dívida de
  navegação não crescer e o AI-edit não ficar arriscado.

**Ajuste na estratégia §4 (consequência da revisão):** `agent_id` sai da Fase 0 como item
pequeno e vira **fatia estrutural dedicada** (provável Fase 1, antes de abrir p/ N agentes
concorrentes). Fase 0 continua: subir na VPS (http já pronto) + nginx+OAuth2 + migração
seletiva — mas o acesso multi-agente concorrente só depois de R1+R2 resolvidos. Avaliar
split do engine (R3) como refactor preparatório antes das features novas.

**Conclusão das 2 análises (autor + independente):** EVOLUIR é consenso. Recomeçar
desperdiçaria state-machine data-driven + gate tipado já existente + transport http +
~3933 LOC testadas. MAS a evolução tem 2 obras estruturais reais (agent_id multi-tenant,
concorrência) — não é ajuste trivial. Tratar por fatias, com os 1595 LOC de teste como rede.
