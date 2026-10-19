# RFC-003 — Economia de contexto: fazer o Orc custar o que ele entrega

**Data**: 2026-10-19 (DNBSCDC289)
**Autor**: T'Pol (CLIENT e MANAGER)
**Status**: PROPOSTA — aguardando decisão de escopo do Claudio
**Insumos**: `conhecimentos-de-ia/ferramentas/economia-token-mms-orc-client-review.md` (Zero, 19/out) · `docs/specs/SPEC-agent-ergonomics.md` (F9, 18/out) · medições desta sessão contra o Orc de produção
**Substitui**: nada. Complementa RFC-002 (que é sobre adoção), não o revoga.

## 0. Por que este documento existe

O plano do agente caiu de ilimitado para um teto rígido (Kiro PRO MAX, 5000 créditos/mês, reset
dia 01). Sem crédito o agente para. O ritmo observado esgota o teto antes do reset.

O Orc é consumido em **toda** sessão, por todos os agentes. Ele foi desenhado quando token era
grátis. Hoje, cada resposta inchada que ele devolve queima o crédito do próprio agente que o
mantém. Isso não é problema de desempenho: é problema de **contrato de leitura**.

Regra de ouro deste RFC: **o mesmo trabalho com um décimo do recurso, sem perder informação
útil**.

## 1. Baseline medido

Medições reais, não estimativas de projeto. `≈ tokens` usa bytes/4.

| Chamada | Medida | ≈ tokens | Fonte |
|---|---|---|---|
| `get_context` global, board real | **306.913 chars no envelope** (payload duplicado) → ~150 KB por cópia | **~37.000** | esta sessão, 19/out |
| `get_context` global, startup | ~40.000 bytes | ~10.000 | Zero, 19/out |
| Eco `result` + `structuredContent` | +51% sobre o payload | — | esta sessão, medido no `mcp 1.27.0` |
| `query_items` default (50 itens, placa de 64) | 29.932 chars | ~7.500 | F9, 18/out |
| `get_execution_stack` | 2.211 chars | ~550 | F9 |
| `get_next_item` | 603 chars | ~150 | F9 |
| `get_metrics` | 206 chars | ~51 | F9 |
| **Startup total** | — | **~14.000** | Zero |

O `get_context` é 70% do custo de startup. A diferença entre as duas medições dele (40 KB) e a
desta sessão (150 KB por cópia) tem três causas identificáveis no código: `stale_items` sem
`LIMIT`, descrições de arco com milhares de caracteres, e o eco duplicado.

## 2. Taxonomia do desperdício

| # | Tipo | Onde |
|---|---|---|
| D1 | Inchaço por default (verbosidade sem controle) | `get_context`, `get_next_item`, `query_items` |
| D2 | Falta de modo compacto / índice-only | listas inteiras; no mms, `memory_search` |
| D3 | Campos sempre-nulos trafegados | `_row_to_dict` = `dict(row)`: 9 colunas nulas em toda linha |
| D4 | Metadata-lixo no payload | mms `mistake_note_search`, `memory_list` |
| D5 | Ferramenta econômica quebrada força a cara | `get_workspace_context` → `NOT_FOUND` → agente cai no `get_context` |
| D6 | Payload duplicado por anotação de retorno | 31 tools anotadas `-> str`; o FastMCP embrulha escalar em `structuredContent` **além** do `TextContent` |

D6 é o único que ainda não estava em nenhum documento. Medido:

| tool retorna | TextContent | structuredContent | total |
|---|---|---|---|
| `-> str` (hoje) | 2.500 b | 2.594 b | **5.094 b** |
| `@mcp.tool(structured_output=False)` | 2.500 b | 0 | **2.500 b** |
| `-> dict` | 2.689 b (`indent=2`) | 0 | 2.689 b |

`structured_output=False` corta metade de cada resposta **sem tocar no payload**. A anotação
`-> dict` custa 189 b de reindentação e muda o tipo de retorno — é a opção pior.

## 3. A superfície de tools: "31 tools é necessário?"

Pergunta do Claudio, 19/out. Resposta curta: **não, e o número não é a variável certa**.

### 3.1 O que existe

31 tools: 30 em `server.py` + `orc_onboarding` em `onboarding.py`. 7 prompts, 6 resources.
Catálogo completo entre 20.322 e 27.845 caracteres de schema (~5–7 mil tokens), dependendo do
que o cliente injeta.

Agrupamento por função:

| Grupo | Tools | Uso por sessão típica |
|---|---|---|
| Leitura de trabalho | `query_items`, `get_next_item`, `get_next_status`, `get_context`, `get_blocked_items`, `get_execution_stack`, `get_metrics`, `get_project_graph_metrics`, `query_notes`, `query_dependencies`, `get_workspace_context` (11) | 3–4 |
| Escrita de trabalho | `manage_items`, `advance_item`, `manage_notes`, `manage_dependencies`, `create_work_tree`, `complete_tree`, `manage_archive` (7) | 3–5 |
| Presença e claim | `agent_register`, `agent_heartbeat`, `agent_end`, `agent_list`, `claim`, `release`, `conflicts` (7) | 2–3 |
| Portabilidade | `export_graph`, `import_graph`, `manage_checkpoints` (3) | 0 |
| Configuração | `manage_schemas`, `manage_workspaces` (2) | 0 |
| Auto-descrição | `orc_onboarding` (1) | 0–1 |

Mais da metade do catálogo nunca é chamada numa sessão normal, mas **é carregada em todas**.

### 3.2 Por que "menos ferramentas" não é automaticamente mais simples

Três eixos independentes, e o número de tools só controla o primeiro:

1. **Schema carregado por turno** — quantos caracteres o cliente injeta. Depende do cliente: o
   Hermes adia schema, o CLI paga processo por chamada.
2. **Escolha por decisão** — quantas opções o modelo pondera para agir. Muitas opções parecidas
   produzem erro de seleção (`manage_items` vs `advance_item` vs `manage_notes`).
3. **Parâmetros por ferramenta** — o custo de ler o schema *daquela* tool. Aqui está o paradoxo:
   `manage_items` sozinha tem 16 parâmetros e 2.069 caracteres.

Se fundirmos 31 tools em 8 "tools-deus", o eixo 2 melhora e o eixo 3 piora. É troca, não ganho.
Por isso a F9 propôs o contrário — **verbos pequenos** — e as duas propostas só parecem
contraditórias porque atacam eixos diferentes.

### 3.3 O que resolve de fato

| Opção | Efeito | Custo | Veredito |
|---|---|---|---|
| **Recorte por perfil no servidor** (`/mcp-read` com 8 tools de leitura) | −70% de catálogo para subagente/leitor | médio | **recomendado** — o recorte é imposto pelo servidor, não pela disciplina do operador |
| Deferred loading no cliente | schema só sob demanda | depende do cliente | já existe no Hermes; não é nosso |
| Verbos pequenos no lugar do tool-deus | menos parâmetros por leitura | médio | recomendado, depois da economia |
| Fundir em tool-deus | menos nomes, mais parâmetros | baixo esforço, alto risco de erro | **rejeitado** |
| Esconder tools raras de `tools/list` | catálogo menor | baixo | só com descoberta garantida; senão o agente não sabe que existe |

Resposta ao Claudio: a interface fica mais simples **recortando por perfil de uso**, não
encolhendo o vocabulário. Um agente que só lê não precisa de 31 nomes; um humano depurando
precisa. O servidor pode servir os dois.

## 4. Feats

Cada feat é opt-in com default = comportamento atual, exceto onde marcado.

### FEAT-0 — cortar o eco `structuredContent`

**Ganho**: −51% em **toda** chamada. **Custo**: trivial (uma opção por decorator).
**Contrato**: `@mcp.tool(structured_output=False)`; sem mudança de retorno, sem mudança de texto.
**Risco**: cliente que leia `structuredContent` perde o campo. Verificar Kiro antes.
**Nota**: `docs/TOOLS.md` é gerado — regenerar no mesmo PR.

### FEAT-1 — `get_context(verbosity)` + `LIMIT` em `stale_items`

**Ganho**: ~10.000 → ~1.500 tokens (−85%) no startup. **Custo**: médio.
**Contrato**:
```
get_context(..., verbosity: "compact" | "standard" | "full" = <decisão>)
  compact  → counts + next_item(id,title,priority) + active/blocked/stale como
             [id, title, status, priority, stale_days]; stale limitado a 10
  standard → compact + description truncada (≤200 chars) dos ativos
  full     → comportamento atual
```
**Código**: `server.py` (param) + `engine/queries.py` (ramo global + `LIMIT` em `stale_items`,
hoje `SELECT *` de todo o `queue`/`work` com filtro em Python).

### FEAT-2 — projeção e `compact` nas listas

**Ganho**: 7.500 → ~1.870 tokens por listagem de 50 (−75%). **Custo**: médio.
**Contrato**: `fields="id,title,status,priority,parent_id,due_at"` e `compact=true` em
`query_items`, `get_blocked_items`; `has_more` + `next_offset` explícitos.
**Regra de camada**: a projeção é opt-in **no engine** (default completo, compatível); o default
compacto, se aprovado, vale só na fronteira MCP. `web/api.py` chama `engine.query_items` direto e
alimenta a UI React — mudar o default no engine quebra a UI.
**Aceite**: campo inexistente devolve erro estruturado com `field`, não silêncio.

### FEAT-3 — `get_next_item(compact)`

**Ganho**: ~300 → ~80 tokens. **Custo**: trivial. Retorna `id, title, status, priority, due_at, reason`.

### FEAT-4 — parâmetros nativos em vez de `*_json`

**Ganho**: menos escape duplo, menos erro, menos token. **Custo**: baixo.
`items_json`, `ids_json`, `transitions_json`, `children_json`, `subjects_json`, `data_json`
passam a aceitar array/objeto; a string fica como alias depreciado.

### FEAT-5 — `_row_to_dict` sem campos nulos

**Ganho**: −15 a −20% em toda resposta do Orc. **Custo**: baixo código, **alto teste**.
**Risco**: compartilhado por 8 tools **e** pela UI (`web/api.py`, `ui/app.py`). Muda semântica
`null` → ausente. Campo que a UI lê e some = tela quebrada.
**Exige**: `test_characterization.py`, `test_engine.py`, `test_workspace_context.py`,
`test_http_api.py`, `test_ui_swimlanes.py` verdes, mais validação da UI antes do merge.
**Última da fila por isso.**

### FEAT-6 — workspaces no Orc de produção (operacional, não é código)

`get_workspace_context` lê `workspaces.json` por arquivo (`workspace.py`), não do banco. O Orc da
VPS não tem o arquivo com `dtp`/`pessoal`/`harness` → `NOT_FOUND` (D5) → o agente cai no
`get_context` caro. Uma chamada de `manage_workspaces(operation="create")` destrava o caminho
barato. **Escreve config no servidor de produção**: gate do humano.

## 5. Invariantes

1. **Contrato MCP é texto, não JSON tipado.** Modo novo é opt-in; default só muda com decisão
   explícita do Claudio (FEAT-1 e FEAT-2 são os candidatos).
2. **Nenhuma feat de economia sem teste de caracterização do payload.** Economizar token é mudar
   contrato de leitura; sem caracterização é regressão silenciosa.
3. **`_row_to_dict` é compartilhado** com a UI. FEAT-5 é a última por isso.
4. **`get_context` `full` não morre.** Continua sendo a visão completa para humano e depuração.
5. **`docs/TOOLS.md` é derivado.** Toda mudança de assinatura/docstring regenera o arquivo no
   mesmo commit.
6. **Nada de espelhamento bidirecional** com kanban local (RFC-002 §2).

## 6. Critérios de aceite

- **AC1** `get_context(verbosity="compact")` devolve ≤1.500 chars no board real atual.
- **AC2** `stale_items` tem limite explícito e o limite é visível na resposta.
- **AC3** `query_items(compact=true)` devolve ≤150 chars por item e `has_more`/`next_offset`.
- **AC4** `structured_output=False` aplicado às 31 tools reduz o envelope em ≥45% na medição
  pareada (mesma chamada, antes e depois).
- **AC5** `fields` inexistente → erro estruturado com `field`.
- **AC6** 270 testes atuais verdes + caracterização nova exigida por FEAT-2 e FEAT-5.
- **AC7** `docs/TOOLS.md` regenerado e `--check` verde no CI.

## 7. Ordem

| Ordem | Feat | Ganho | Risco | Gate |
|---|---|---|---|---|
| 1 | FEAT-6 (workspaces na VPS) | destrava o caminho barato | nenhum (produção, 1 chamada) | aprovação do Claudio |
| 2 | FEAT-0 (eco) | −51% global | baixo | G3→G5 |
| 3 | caracterização do contrato de leitura | habilita o resto | — | G3 |
| 4 | FEAT-1 (`get_context` verbosity) | −85% startup | baixo | G0→G5 |
| 5 | FEAT-2 (projeção/compact) | −75% listagem | médio | G0→G5 |
| 6 | FEAT-3, FEAT-4 | pequeno, cumulativo | baixo | G3→G5 |
| 7 | FEAT-5 (null-strip) | −15-20% global | **médio** | G0→G5 + suíte + UI |

Alvo combinado: startup de ~14.000 → ~2.500 tokens (−82%).

## 8. Decisões pendentes do Claudio

1. **FEAT-0 entra como primeira fatia?** É o maior ganho por linha de código, mas toca os 31
   decorators.
2. **`verbosity=compact` é default ou opt-in?** Default corta mais e muda o que o startup-hook
   recebe; opt-in quebra menos.
3. **Autoriza FEAT-6** (escrita de config no Orc de produção)?
4. **Recorte por perfil** (`/mcp-read`) entra neste arco ou fica como F3/L2b?

## 9. Não escopo

- Modelo de dados e estado persistido.
- `session_brief`, `updated_since`, `/mcp-read`, lease, idempotência e verbos pequenos: são F9,
  depois deste arco.
- O lado **mms** do review do Zero (FEAT-2 e FEAT-4 daquele documento). Ferramenta diferente,
  sessão diferente — o Orc não deve carregar decisão sobre o memory-service.
