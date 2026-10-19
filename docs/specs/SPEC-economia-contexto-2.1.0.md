# SPEC — Economia de contexto (RFC-003), release 2.1.0

**Origem**: `docs/rfc/RFC-003-economia-de-contexto.md` (19/out). Esta spec não substitui o RFC —
converte as feats em requisitos EARS verificáveis e define o que fecha cada gate.
**Autor**: T'Pol (MANAGER e CLIENT do Orc)
**Status**: aprovada para execução em 19/out/2026 — Claudio autorizou "dentro do nosso gate de dev".
**Versão alvo**: 2.1.0 (MINOR: tudo aditivo, comportamento atual permanece o default).

## 0. Escopo e ordem

| # | Etapa | Item no board | Gate |
|---|---|---|---|
| A | Caracterização do contrato de leitura | `7e96f7bb` | G3 |
| B | FEAT-1 — `get_context(verbosity)` + `LIMIT` em `stale_items` | `56af92fa` | G0→G5 |
| C | FEAT-6b — workspaces no banco | `48474083` | G0→G5 |
| D | FEAT-2 — projeção e `compact` nas listas | `5934535f` | G0→G5 |
| E | Release 2.1.0 | `c79cc99c` | G6 + E2E de fio contra produção |

Dependências: A bloqueia B e D. C é independente de A. E exige A, B, C e D concluídas.

Fora de escopo desta release: FEAT-3 e FEAT-4 (2.2.0), FEAT-5 (última da fila do RFC), recorte por
perfil `/mcp-read` (F9).

## A. Caracterização do contrato de leitura

A2, A3 e A4 existem porque economizar token é **mudar contrato de leitura**: sem régua pareada, a
regressão é silenciosa (RFC §5, invariante 2).

**R-A1** — O repositório *shall* manter um baseline versionado (`tests/data/reading_contract_baseline.json`
mais os payloads em `tests/data/reading_contract/`) com, para cada chamada de rotina da régua
(`scripts/measure_payload.py`, 10 chamadas: as 6 do RFC e as variações de lista e de notas), o
tamanho em caracteres e o `sha256` do payload **normalizado** medido sobre a placa determinística.

**R-A1b** — A caracterização *shall* distinguir duas medidas e documentá-las: o `chars` do baseline é
o do payload **normalizado** (detecta mudança de forma); o tamanho **real** em bytes por chamada
continua sendo o da tabela e do `--json` da régua, que não normalizam — é esse número que o RFC cita,
com `bytes/4` como conversão de tokens.

**R-A2** — *While* a placa e a versão do servidor não mudarem, o payload de cada chamada de rotina
*shall* ser byte-idêntico ao baseline registrado.

**R-A3** — *When* um payload divergir do baseline, o teste *shall* falhar reportando a ferramenta, o
tamanho medido, o tamanho esperado e o offset da primeira divergência.

**R-A4** — *Where* `ORC_UPDATE_BASELINE=1` estiver definido, o teste *shall* regravar o baseline; em
qualquer outro caso *shall not* escrever no disco.

**R-A5** — O teste *shall* normalizar campos voláteis (ids, timestamps) por substituição
determinística documentada no topo do arquivo, e *shall not* omiti-los silenciosamente da medição.

**R-A6** — A caracterização *shall* rodar na suíte normal (`pytest tests/`), não como script manual.

## B. FEAT-1 — `get_context(verbosity)` e `LIMIT` em `stale_items`

Decisão do Claudio (19/out): **opt-in**. O default não muda.

**R-B1** — `get_context` *shall* aceitar `verbosity` com os valores `compact`, `standard` e `full`;
quando omitido, o valor efetivo *shall* ser `full`.

**R-B2** — *If* `verbosity` receber valor fora do enum, *then* o servidor *shall* responder erro
estruturado com `code`, `message` e `field="verbosity"`.

**R-B3** — *When* `verbosity="compact"`, o payload *shall* conter apenas `counts`,
`next_item` reduzido a `id`, `title` e `priority`, e as listas `active`, `blocked` e `stale` com
itens representados por `[id, title, status, priority, stale_days]`, onde `id` é o **prefixo de 8
caracteres** — UUID completo custa 36 por item e sozinho estoura o teto do AC-B1; `resolve_short_id`
já aceita 4+ caracteres na entrada.

**R-B4** — *When* `verbosity="compact"`, `stale` *shall* trazer no máximo 10 itens e a resposta
*shall* informar `stale_total` e `stale_limit`, para que o truncamento seja visível e não silencioso.

**R-B5** — *When* `verbosity="standard"`, o payload *shall* ser o de `compact` acrescido da
`description` truncada em 200 caracteres dos itens ativos.

**R-B6** — *When* `verbosity` for `full` ou ausente, o payload *shall* ser byte-idêntico ao da
versão 2.0.1 — verificado por R-A2, não por inspeção visual.

**R-B7** — `stale_items` *shall* aplicar limite na consulta SQL; *shall not* materializar todo o
`queue` e todo o `work` para filtrar em Python.

## C. FEAT-6b — workspaces no banco

Origem da correção: Claudio, 19/out — "workspace não deveria ser banco e facilmente gerenciável?".
A versão anterior tratava como passo de deploy o que é defeito de substrato.

**R-C1** — Workspaces *shall* ser persistidos em tabela `workspaces` do mesmo arquivo SQLite dos
work items, com migração aditiva.

**R-C2** — A API pública de `workspace.py` (`list_workspaces`, `create_workspace`, `update_workspace`,
`delete_workspace`, `get_workspace_tags`, `get_workspace_config`) *shall* preservar assinaturas e
semântica; chamadores (`engine/workspace_view.py`, `engine/portability.py`) *shall not* ser alterados.

**R-C3** — `create_workspace` e `update_workspace` *shall* gravar `created_by` e `updated_by` com o
`agent_id` resolvido por requisição (mesmo mecanismo de items/notes/dependencies).

**R-C4** — *When* `export_graph` for chamado, o payload *shall* incluir os workspaces; `import_graph`
*shall* restaurá-los tanto em `mode="merge"` quanto em `mode="replace"`.

**R-C5** — *Where* existir um `workspaces.json` legado e a tabela `workspaces` estiver vazia, o
sistema *shall* importá-lo uma única vez; *if* a tabela já contiver linhas, *then shall not* importar
por cima.

**R-C6** — Escritas concorrentes de workspaces *shall not* perder linhas: cada operação *shall* ser
transacional, sem o padrão ler-dict-inteiro/regravar-arquivo-inteiro.

**R-C7** — `get_workspace_context` *shall* responder a partir do banco, sem depender de arquivo
provisionado no deploy — eliminando a causa raiz do D5.

## D. FEAT-2 — projeção e `compact` nas listas

**R-D1** — `query_items` e `get_blocked_items` *shall* aceitar `fields`, com nomes de coluna
separados por vírgula.

**R-D2** — *Where* `fields` for informado, a resposta *shall* conter apenas os campos pedidos, na
ordem pedida.

**R-D3** — *If* `fields` citar campo inexistente, *then* o servidor *shall* responder erro
estruturado nomeando o campo; *shall not* ignorar em silêncio.

**R-D4** — *Where* `compact=true`, cada item *shall* ocupar no máximo 150 caracteres no payload.

**R-D5** — Listas *shall* devolver `has_more` e `next_offset` explícitos quando houver mais
resultados, dispensando o agente de inferir por `len(result) == limit`.

**R-D6** — A projeção *shall* ser opt-in no engine (default completo); `web/api.py` e a UI React
*shall not* mudar de comportamento. Um default compacto, se aprovado no futuro, vale apenas na
fronteira MCP.

## Critérios de aceite (verificáveis)

| AC | Requisito | Como se verifica |
|---|---|---|
| AC-A1 | R-A1..A6 | `pytest tests/test_reading_contract.py -q` verde; baseline presente no git |
| AC-A2 | R-A3 | corromper um hash do baseline e observar a falha com offset; restaurar em seguida |
| AC-B1 | R-B3, R-B4 | `get_context(verbosity="compact")` ≤ 1.500 chars no board real; `stale_total` e `stale_limit` presentes |
| AC-B2 | R-B6 | caracterização A prova byte-identidade do default `full` |
| AC-B3 | R-B7 | inspeção do SQL emitido: `LIMIT` presente; nenhum `SELECT *` de todo o `queue`/`work` |
| AC-B4 | R-B2 | chamada com `verbosity="verbose"` devolve erro estruturado com `field` |
| AC-C1 | R-C4 | round-trip `export_graph` → banco vazio → `import_graph` preserva os workspaces |
| AC-C2 | R-C3 | `create_workspace` com `X-Agent-ID` grava `created_by`; verificado por SQL, não por resposta |
| AC-C3 | R-C5 | `workspaces.json` legado importado na primeira abertura e ignorado na segunda |
| AC-C4 | R-C7 | `get_workspace_context` responde com banco que tem workspaces e nenhum arquivo ao lado |
| AC-D1 | R-D4 | `query_items(compact=true)` ≤ 150 chars por item |
| AC-D2 | R-D3 | `fields="id,naoexiste"` devolve erro com `field` |
| AC-D3 | R-D5 | `has_more`/`next_offset` corretos em limite parcial e total |
| AC-E1 | RFC §6 AC6 | suíte completa verde; `ruff check` e `ruff format --check` limpos |
| AC-E2 | RFC §6 AC7 | `scripts/generate_tools_doc.py --check` verde; `docs/TOOLS.md` regenerado no mesmo commit |
| AC-E3 | release | cliente MCP real contra produção após deploy: `get_context(verbosity="compact")` e `query_items(compact=true)` medidos e comparados ao baseline do RFC |
| AC-E4 | release | `/health` reporta 2.1.0; `CHANGELOG.md` com Added/Changed; tag `v2.1.0` só após "vai" explícito |

## Diário de gate

| Gate | Etapa | Veredito | Evidência |
|---|---|---|---|
| G0 (desenho) | — | pendente | — |
| G3 (RED) | A | **fechado** 19/out | baseline corrompido em 1 char → falha com "primeira diferença no offset 19 (esperado 22132, medido 22131)"; restaurado → verde |
| G4 (GREEN) | A | **fechado** 19/out | `282 passed`; `ruff check` e `format --check` limpos; determinismo provado por diff de duas execuções da régua |
| G5 (review) | A | **fechado** 19/out | review independente: APPROVED-WITH-NITS, 2×P1 + 4×P2; todos os P2 e o P1 de normalização corrigidos em `c131573` com 10 casos parametrizados |

Preenchido ao longo da execução. Gate não fecha por relato de subagente: fecha por medição do
MANAGER contra o caminho real de execução.

## Invariantes que valem para todas as etapas

1. Nenhuma feat de economia sem caracterização verde (RFC §5.2).
2. `get_context` `full` não morre: é a visão de humano e de depuração.
3. `docs/TOOLS.md` é derivado — regenerar no mesmo commit de qualquer mudança de assinatura.
4. `_row_to_dict` (FEAT-5) é compartilhado com a UI e fica para o fim da fila.
5. Nada de espelhamento bidirecional com kanban local (RFC-002 §2).
