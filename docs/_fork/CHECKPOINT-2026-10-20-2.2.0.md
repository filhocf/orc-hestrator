# Checkpoint — Orc 2.2.0 em construção (20/out/2026, ~07:45)

**Sessão encerrada por orçamento de contexto (≈370k, faixa CRÍTICA).**
Retomar daqui numa sessão nova, não continuar no histórico velho.

## ⚠️ O REPOSITÓRIO MUDOU DE LUGAR

```
/home/claudio/git/orc/            ← agora é DIRETÓRIO PAI, não é repo
├── orc1/                         ← REPO PRINCIPAL (branch main). TRABALHAR AQUI
├── orc-wt-feat1b/
├── orc-wt-feat2/
└── orc-wt-feat6b/
```

Qualquer comando, spec ou memória que diga `~/git/orc` está **desatualizado**:
o repo é **`~/git/orc/orc1`**.

**Pitfall imediato:** `.venv` herdou shebang do path antigo
(`#!/home/claudio/git/orc/.venv/bin/python`) e o pytest falhou com
`ModuleNotFoundError` + conftest fantasma. Correção aplicada:
`rm -rf .venv .pytest_cache && uv sync --extra test --extra ui`.

## Estado do código

`main` = `eb4074f`. Suíte em **359 passed** ao fim da fatia C (venv novo após isso).

| Commit | Fatia |
|---|---|
| `058fba2` | spec 2.1.1 (G0) |
| `d246f54` | spec 2.2.0 — 4 fatias, uma release (G0) |
| `7f23d9a` | **A** `_insert_rows` pela união das chaves ✅ |
| `6b3da6a` | **B** `get_next_item(compact)` + `reason` ✅ |
| `eb4074f` | **C** parâmetros nativos (`_json_arg`) ✅ |
| — | **D** `_row_to_dict` null-strip — **EM ANDAMENTO, NÃO COMMITADA** |

### Frames fechados (evidência)

- **A**: RED com 5/7 falhando pelo motivo certo (2 passavam: homogêneo e chave
  desconhecida); GREEN de uma linha (`present = {k for row in rows for k in row}`).
  Cobre `work_items`, `notes`, `dependencies`. CHANGELOG `### Fixed`.
- **B**: 7 de 8 falhavam por `TypeError`; `compact` devolve id(8)/title(≤60)/
  status/priority/due_at/**reason** (`in progress` | `overdue` | `priority:<n>`).
  **AC medido: 177 chars ≈ 44 tok contra ~300** (−85%). Teto do AC ajustado
  150 → 180, com o motivo registrado na spec (caber em 150 exigiria título de
  33 chars e o agente voltaria a pedir o item completo).
- **C**: **não houve RED antes** — erro de gate registrado no commit; a prova de
  mordida foi feita revertendo `server.py` ao HEAD (8 de 10 falham). R-C3 da spec
  estava mal formulado ("ambos vierem" pressupunha um segundo parâmetro): o RFC
  amplia o tipo do **mesmo** parâmetro; corrigido para R-C3b/R-C4.

### Fatia D — o que está no working tree, sem commit

```
M src/task_orchestrator/engine/base.py      _row_to_dict(row, drop_nulls=False)
M src/task_orchestrator/engine/items.py     query_items -> drop_nulls=True
M src/task_orchestrator/engine/queries.py   get_blocked_items, active, recent, stale -> True
?? tests/test_null_strip.py                 6 testes; 5 passam, 1 falha
```

Ganho medido no board real antes de implementar: **`get_context` full −15,8%**
e **`query_items(50)` −13,3%** (AC-D1 exigia ≥12% → passa).

**Falha em aberto:** `test_get_blocked_items_omits_nulls` — o `blocked` do
`get_context` vem de `get_blocked_items` (que já aplica strip), mas a lista
`blocked` do caminho full ainda carrega nulos. Investigar: provavelmente
`get_blocked_items` retorna itens de `get_next_item` internos ou o caminho
`blocked` do full usa outra construção. **Não é o teste que está errado** — o
`AssertionError` aponta chaves nulas reais.

Nota de teste: `summary` e `description` **não** entram na lista de campos
anuláveis — o schema dá default `''`, e string vazia é valor, não nulo. Omiti-las
mudaria o shape de campo que a UI lê sempre.

## O que falta na fatia D

1. Corrigir o caminho `blocked` do `get_context` full (acima).
2. **Regravar o baseline da caracterização** — o strip muda o payload por
   desenho. Regravar com `ORC_UPDATE_BASELINE=1` e registrar o motivo no commit.
3. AC-D2: `test_characterization`, `test_engine`, `test_workspace_context`,
   `test_http_api`, `test_ui_swimlanes` verdes.
4. AC-D3: validar a UI na VPS depois do deploy (Kanban + arcos, sem erro de console).
5. CHANGELOG `### Changed` (R-G1) + `TOOLS.md` se assinatura mudar.

**Critério de aborto (spec §9):** reprovou AC-D2/AC-D3 e sem conserto em 30 min →
sai da 2.2.0 e vira 2.3.0.

## Depois da D

G5 (`tuvok`, um review cobrindo A–D) → G6 (verificação própria + **teste a quente
na VPS** com snapshot `VACUUM INTO`) → tag `v2.2.0` + PyPI **só com "vai"**.

Board: raiz `484d3c7f`; A `bc0c981a`, B `6b712aee`, C `9aed9439`, D `4b03bf04`
(cadeia de dependências A→B→C→D). Release 2.1.0 e RFC-003 já fechados.

## Erro de método a corrigir na próxima sessão

O Claudio cobrou delegação: **três fatias foram feitas sem subagente**, e a D —
varredura de consumidores na UI (`web/api.py`, `ui/app.py`) — era exatamente o
tipo de tarefa delegável. O modelo dos subagentes mudou para
`deepseek-v4.1-flash` (Lia/Nous Portal), com contexto maior que o 27B que falhou
duas vezes em 19/out, então a desculpa de "subagente estoura contexto" não vale
mais para escopo cirúrgico. **Delegar a varredura da UI e a correção do `blocked`
antes de assumir tudo.**
