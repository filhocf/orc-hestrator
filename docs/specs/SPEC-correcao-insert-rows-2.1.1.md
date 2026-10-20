# SPEC — Correção de `_insert_rows` (Orc 2.1.1, PATCH)

Status: **G0 aberto** (20/out/2026)
Origem: item `54951e98` — achado do review amplo do `tuvok` (15/out), marcado
`[ALTO latente]`. Escopo reduzido após leitura do código em 20/out.
SemVer: **PATCH** (2.1.0 → 2.1.1). Nenhuma assinatura pública muda; nenhum
comportamento documentado muda. Corrige perda silenciosa de dados.

## 1. Contexto

`engine/portability.py:86` insere lotes de linhas vindos de um export:

```python
cols = [c for c in columns if c in rows[0]]      # só a PRIMEIRA linha decide
values = [tuple(row.get(c) for c in cols) for row in rows]
```

A lista de colunas é derivada de `rows[0]`. Consequências:

- se a linha 0 não traz uma coluna que as demais trazem, a coluna **desaparece
  do INSERT inteiro** — o valor das outras linhas é descartado;
- `row.get(c)` para coluna ausente na linha vira `NULL`, indistinguível de
  "valor nulo de verdade";
- a falha é **silenciosa**: `import_graph` devolve sucesso, o item entra, e o
  dado que faltava simplesmente não está lá.

O caminho nasce em `import_graph` → `_insert_rows(conn, "work_items" | "notes" |
"dependencies", ...)`, chamado com dados de `export_graph`. Um export é
homogêneo por construção, mas a entrada de `import_graph` é **dado externo**
(JSON que o usuário pode compor, editar ou concatenar de duas origens), e a
função não valida homogeneidade nem usa a união das chaves.

### Por que PATCH e não "deixa como está"

Perda silenciosa de dado é a pior classe de defeito: não há erro, não há log, e
o usuário só descobre quando o dado já não existe. É a mesma classe do
`import_graph(mode="replace")` que apagava workspaces (corrigido em `4bfa89a`).

## 2. Fora de escopo — e uma reclassificação

**`848eea0b` ("import_graph merge nunca faz UPDATE") NÃO é bug.** O docstring da
engine (linha 198) e o da tool (linha 792) declaram: *"mode='merge': insert rows
that don't exist (skip on conflict)"*. O comportamento atual **é** o contrato.
Mudá-lo para UPSERT é mudança de comportamento observável → seria **MINOR**,
não PATCH, e precisa de decisão de produto (e de um nome próprio, ex. `mode="sync"`).
Fica registrado como candidato ao 2.2.0; **não entra no 2.1.1**.

Fora de escopo também: validação de schema do payload, deduplicação, migração de
formato de export, e qualquer alteração em `export_graph`.

## 3. Requisitos (EARS)

Sujeito = componente. Uma ação por frase. Sempre verificáveis.

**R-A1 (união de chaves).**
WHEN um lote contiver linhas com conjuntos de chaves diferentes,
THE `_insert_rows` SHALL derivar as colunas do INSERT da **união** das chaves de
todas as linhas do lote, preservando a ordem das colunas da tabela.

**R-A2 (valor preservado).**
WHEN uma coluna existir em alguma linha do lote mas não na primeira,
THE linha que a possui SHALL ser inserida com esse valor, e não com `NULL`.

**R-A3 (ausência explícita).**
WHEN uma linha não trouxer determinada coluna do lote,
THE `_insert_rows` SHALL inserir `NULL` naquela coluna para aquela linha apenas.

**R-A4 (coluna desconhecida).**
WHEN o lote trouxer chave que não corresponde a coluna da tabela,
THE `_insert_rows` SHALL ignorá-la sem erro, como hoje — a tabela continua sendo
a autoridade sobre o que existe.

**R-A5 (homogeneidade preservada).**
WHEN todas as linhas do lote tiverem as mesmas chaves,
THE SQL gerado SHALL ser equivalente ao atual e o resultado SHALL ser
byte-idêntico — a correção não pode alterar o caminho que já funciona.

**R-A6 (contrato de retorno).**
THE `import_graph` SHALL continuar devolvendo o mesmo formato de resultado nos
modos `merge` e `replace`; a correção não acrescenta campo nem muda contagem.

## 4. Acceptance criteria

| AC | Critério | Medida |
|---|---|---|
| AC-1 | Lote heterogêneo preserva valor fora da linha 0 | teste: linha 0 sem `summary`, linha 1 com `summary="x"` → após import, `summary == "x"` (hoje: `NULL`) |
| AC-2 | Lote heterogêneo não perde coluna | as duas linhas existem com `title` correto e `summary` conforme cada uma |
| AC-3 | Coluna ausente vira NULL só naquela linha | linha 0 com `summary`, linha 1 sem → linha 1 `NULL`, linha 0 com valor |
| AC-4 | Chave desconhecida é ignorada | import com `{"campo_inexistente": 1}` não levanta; item entra |
| AC-5 | Homogêneo idêntico ao atual | teste de caracterização do import: mesmo payload → mesmas linhas, mesmos valores, mesma contagem |
| AC-6 | Todos os três alvos cobertos | `work_items`, `notes` e `dependencies` exercitados com lote heterogêneo |
| AC-7 | Suíte inteira verde | `uv run pytest tests/ -q` sem falha; contagem ≥ 334 |
| AC-8 | Nada muda em export | `export_graph` byte-idêntico antes/depois (mesma sessão, mesmo banco) |

## 5. Invariantes

- Nenhuma assinatura pública alterada (`import_graph`, `export_graph`, tools).
- `validate_fields`/`ToolError` intactos; erro de jogador continua estruturado.
- `INSERT OR IGNORE` mantido: conflito de PK continua sendo "já existe, pula".
- Nenhuma migração de schema. `user_version` continua 1.

## 6. Gates

| Gate | Etapa | Evidência exigida |
|---|---|---|
| G0 | esta spec | EARS acima revisada; escopo e reclassificação de `848eea0b` registrados |
| G1 | contrato congelado | AC-1..AC-8 acordados **antes** do RED |
| G2 | desenho | união de chaves + ordem da tabela; sem reescrever `_insert_rows` para ORM |
| G3 | RED | teste novo falha **por motivo certo** em 2.1.0 (mostra `NULL` onde devia ter valor) |
| G4 | GREEN | correção mínima; suíte verde; `ruff` limpo |
| G5 | review independente | persona `tuvok`, escopo cirúrgico: `portability.py` + teste novo |
| G6 | verificação | agente roda por conta própria; depois **teste a quente** na VPS com snapshot do banco de produção e, só então, PyPI |
| — | publicação | tag `v2.1.1` **apenas** com "vai" explícito |

## 7. Riscos

| Risco | Mitigação |
|---|---|
| União de chaves mudar a ordem das colunas e quebrar caract. | ordem vem de `PRAGMA table_info`, não do dict (R-A5 + AC-5) |
| Lote muito grande com chaves muito distintas gerar SQL enorme | colunas são limitadas pelo schema da tabela (R-A4) |
| Correção mascarar defeito vizinho (`merge` sem UPDATE) | declará-lo explicitamente fora de escopo, com reclassificação |
| Teste passar por acidente com dados homogêneos | AC-1 usa lote deliberadamente heterogêneo, e o RED roda contra 2.1.0 |
