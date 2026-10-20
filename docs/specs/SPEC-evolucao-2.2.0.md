# SPEC — Orc 2.2.0 (MINOR): fechamento do RFC-003 + correção de perda silenciosa

Status: **G0 aberto** (20/out/2026)
Absorve: `docs/specs/SPEC-correcao-insert-rows-2.1.1.md` (FIX-A — a spec detalhada
do fix continua sendo a referência dele; o gate é o mesmo).
SemVer: **MINOR** (2.1.0 → 2.2.0). Contém 1 correção de bug + 3 features aditivas.

Decisão do Claudio (20/out): **uma release, não duas.** O 2.1.1 isolado custaria um
ciclo inteiro de deploy para uma correção de horas de trabalho. Fix de perda de
dados vai junto — registrado que, por SemVer estrito, ele "merecia" PATCH, e que
isso é consciente.

Ritmo: **horas.** Fatias curtas, RED→GREEN cada uma, review único no fim (G5),
teste a quente e publicação no mesmo dia.

## 1. Fatias e ordem

| # | Fatia | Tipo | Ganho | Risco |
|---|---|---|---|---|
| A | `_insert_rows` — colunas pela união das chaves | FIX | perda silenciosa | baixo |
| B | `get_next_item(compact)` | FEAT | ~300 → ~80 tok | trivial |
| C | parâmetros nativos em vez de `*_json` | FEAT | menos escape, menos erro | baixo |
| D | `_row_to_dict` sem campos nulos | FEAT | −15 a −20% global | **médio (UI)** |

Ordem execução: **A → B → C → D.** A primeiro porque é corretude. D por último
porque é o único que toca a UI (`web/api.py`, `ui/app.py`).

## 2. Fatia A — correção de `_insert_rows`

Requisitos completos em `SPEC-correcao-insert-rows-2.1.1.md` §3 (R-A1..A6) e
AC-1..AC-8. Resumo do contrato:

- colunas = **união** das chaves de todas as linhas, na ordem de `PRAGMA table_info`;
- coluna ausente numa linha → `NULL` naquela linha apenas;
- chave desconhecida ignorada (a tabela é a autoridade);
- lote homogêneo → SQL equivalente ao atual;
- cobre `work_items`, `notes` e `dependencies`.

## 3. Fatia B — `get_next_item(compact)`

**R-B1.** WHEN `compact=true`, THE `get_next_item` SHALL devolver apenas
`id` (8 chars), `title` (≤60), `status`, `priority`, `due_at` e `reason`
— o motivo pelo qual aquele item é o próximo.

**R-B2.** WHEN `compact` não for informado, THE resposta SHALL ser
byte-idêntica à de 2.1.0 (default preservado; caracterização cobre).

**R-B3.** WHEN não houver item acionável, THE resposta SHALL continuar sendo o
mesmo `null`/vazio de hoje, com o mesmo formato.

**AC-B1.** Payload compacto ≤ **180 chars** (~44 tokens), medido — não estimado.
O RFC estimou ~80 tok com teto de 150 chars, mas as seis chaves fixas com título
legível somam 177: caber em 150 exigiria título de ~33 chars, que deixa de
identificar o item e faz o agente pedir a linha completa, anulando o ganho.
Ganho real: **~300 → ~44 tok (−85%)**.
**AC-B2.** `full` inalterado: caracterização verde sem regravar baseline.

## 4. Fatia C — parâmetros nativos

Alvos: `items_json`, `ids_json`, `transitions_json`, `children_json`,
`subjects_json`, `data_json`.

**R-C1.** WHEN o chamador passar um array/objeto nativo, THE tool SHALL aceitá-lo
sem exigir serialização manual em string.
**R-C2.** WHEN passar string JSON, THE tool SHALL continuar aceitando, como alias
depreciado — nenhum cliente existente quebra.
**R-C3.** WHEN o valor não for nem estrutura nem JSON válido, THE tool SHALL
devolver `ToolError("VALIDATION", ..., <nome do parâmetro>)` — erro que nomeia o
parâmetro, não `JSONDecodeError` cru.

> Correção do requisito original (20/out, na implementação): ele falava em
> "rejeitar quando ambos vierem", pressupondo um segundo parâmetro nativo ao lado
> do `*_json`. O RFC amplia o **tipo do mesmo parâmetro** — não há dois. O que
> precisa de erro explícito é o valor inválido, e é isso que R-C3 exige.

**R-C3b.** WHEN a estrutura vier no tipo errado (ex.: objeto onde se espera
lista), THE erro SHALL dizer o tipo esperado e o recebido.

**R-C4.** WHEN o parâmetro vier vazio (`""`), THE tool SHALL manter o
comportamento histórico (lista/objeto vazio), sem erro.

**AC-C1.** Cada uma das 6 tools aceita nativo e string, com teste por alvo.
**AC-C2.** `docs/TOOLS.md` regenerado; `--check` verde: a assinatura muda, então
a doc derivada muda no mesmo commit.
**AC-C3.** Duplo fornecimento produz erro estruturado, não escolha silenciosa.

## 5. Fatia D — `_row_to_dict` sem nulos (a mais arriscada)

**R-D1.** WHEN um campo for `NULL`, THE dicionário SHALL **omitir** a chave, em
vez de devolver `null` — **exceto** as chaves estruturais de R-D1a.
**R-D1a.** THE chaves estruturais (`id`, `title`, `status`, `priority`,
`created_at`, `created_by`, `updated_at`) SHALL permanecer sempre presentes,
mesmo quando `NULL`: são identidade e proveniência do item, e um consumidor que
as perde não distingue item de stub.
**R-D1b.** WHEN a chave for opcional (`due_at`, `parent_id`, `status_label`,
`previous_status`, `complexity`, `schedule`, `metadata`, `properties`), THE
dicionário SHALL omiti-la quando o valor for `NULL`.
**R-D1c.** THE chaves `summary` e `description` SHALL NOT ser omitidas: o schema
dá default `''` e string vazia é valor, não nulo.
**R-D2.** THE chaves de controle de paginação e contagem (`count`, `has_more`,
`next_offset`, `total`, `*_total`) SHALL permanecer sempre presentes, mesmo
quando zero — omiti-las quebraria consumidores.
**R-D3.** THE UI (`web/api.py`, `ui/app.py`) SHALL continuar funcionando: campo
ausente deve ser lido como falsy, nunca gerar `KeyError`.
**R-D4.** WHEN o consumidor precisar distinguir "ausente" de "nulo", THE
`get_item` (leitura de um item só) SHALL manter as chaves completas — o strip
vale para listas e dashboards, onde o volume está.

**AC-D1.** Redução de payload ≥ **12%** numa sessão típica (`get_context` full +
`query_items(50)`), medido no board real, pareado.
**AC-D2.** `test_characterization`, `test_engine`, `test_workspace_context`,
`test_http_api`, `test_ui_swimlanes` verdes.
**AC-D3.** UI validada na VPS após deploy: Kanban e visão de arcos carregam, sem
erro no console.
**AC-D4.** `get_item` mantém chaves completas (R-D4 provado por teste).
**AC-D5.** Em `query_items`, `get_blocked_items` e no `blocked` do `get_context`,
todo item traz as **7 chaves estruturais** de R-D1a mesmo com `NULL` no banco, e
**omite** as opcionais nulas de R-D1b. Provado por teste com fixture em banco
temporário gravada por SQL com `NULL` explícito.

> Origem de R-D1a..c (20/out/2026): o AC-D2 reprovou em
> `tests/test_http_api.py::test_items_populated_returns_items_with_created_by`
> (`assert 'created_by' in ...`) porque a regra original omitia **toda** chave
> nula. O teste é anterior à fatia: o contrato vigente exige a chave. A regra
> "omitir todo nulo" era larga demais — daí a separação estrutural/opcional.
> **Decisão fechada, não reabrir.**

## 6. Fora de escopo

- **`848eea0b`** (`merge` nunca faz UPDATE) — é contrato documentado; UPSERT exige
  decisão de produto e nome próprio (`mode="sync"`). Não entra.
- Padronizar o vocabulário de `verbosity` entre `get_context` (compact) e
  `get_workspace_context` (minimal) — renomear quebra cliente; fica para 2.3.0.
- Renomear `version` → `schema_version` no export (item `030f5966`): o campo hoje
  reporta a versão do produto. Decidir a semântica é produto, não patch.
- Migrações, schema, workspaces: nada muda.

## 7. Gates (enxutos, não ausentes)

| Gate | Evidência |
|---|---|
| G0 | esta spec + EARS das 4 fatias; escopo e exclusões registrados |
| G2 | desenho por fatia registrado no commit de RED |
| G3 | RED por fatia: teste falha **por motivo certo** em 2.1.0 |
| G4 | GREEN: suíte inteira verde, `ruff` limpo, `TOOLS.md --check` |
| G5 | **um review** (`tuvok`) cobrindo as 4 fatias, escopo cirúrgico |
| G6 | verificação própria + **teste a quente** na VPS com snapshot de produção |
| — | tag `v2.2.0` + PyPI **só com "vai"** |

## 8. Documentação obrigatória (requisito do Claudio, 20/out)

**R-G1.** THE CHANGELOG SHALL registrar **cada mudança** da release, na seção
`[2.2.0]`, no **mesmo commit** que a implementa — não no fim, não "depois".
Fatia sem linha no CHANGELOG não está concluída.

**R-G2.** WHEN a assinatura de uma tool mudar, THE `docs/TOOLS.md` SHALL ser
regenerado no mesmo commit (é derivado; `--check` no CI quebra se divergir).

**R-G3.** THE entrada SHALL dizer o **efeito para quem usa**, não o nome interno
da função: "listas compactas devolvem has_more/next_offset" e não
"adicionado parâmetro em _projection_names".

**R-G4.** WHEN uma fatia for abortada (ver §9), THE CHANGELOG SHALL **não**
mencioná-la, e a spec SHALL registrar o motivo do aborto.

Formato por fatia, dentro de `## [2.2.0]`:
`### Fixed` para a fatia A, `### Added` para B e C, `### Changed` para D.

## 9. Critério de aborto

Se a fatia D (null-strip) reprovar em AC-D2 ou AC-D3 e o conserto não for óbvio
em 30 minutos, ela **sai da 2.2.0** e vira 2.3.0. Publicar A+B+C já entrega
corretude e economia; D é a única que pode quebrar a UI, e release não é lugar
para teimosia.
