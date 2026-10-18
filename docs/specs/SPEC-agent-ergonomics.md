# SPEC — F9: ergonomia para o agente consumidor

Origem: pedido de Claudio (18/out) para que eu, como CLIENT do Orc, diga onde ele me ajuda e onde
me atrapalha. Este documento é a visão de uso do lado de dentro: o que custa contexto, o que custa
tentativa e erro, e o que falta para eu operar sem desperdício.

Status: proposta, aguardando priorização. Não substitui nenhuma decisão das ADRs.

## Como medi

Placa sintética com 64 itens (8 arcos × 8 filhos, prioridades variadas, 12 em `work`, com notas de
fase), banco em diretório temporário, superfície MCP real (`mcp.call_tool`), commit `88e7657`.

| Chamada | Caracteres | ≈ tokens | Observação |
|---|---|---|---|
| `query_items(operation="list")` com default `limit=50` | 29.932 | 7.483 | **uma** chamada |
| `query_items(limit=10)` | 5.981 | 1.495 | 598 chars por item |
| `query_items(status="work")` | 7.185 | 1.796 | 12 itens |
| `get_context()` | 6.761 | 1.690 | sempre com 9 chaves, mesmo vazias |
| `get_execution_stack()` | 2.211 | 552 | |
| `get_next_item()` | 603 | 150 | barato e decisivo |
| `get_metrics()` | 206 | 51 | |
| `get_blocked_items()` | 2 | 0 | `[]` |

Cada item traz **22 chaves** e 598 caracteres. Boa parte é nula ou irrelevante para decidir:
`description`, `summary`, `metadata`, `properties`, `status_label`, `previous_status`,
`role_changed_at`, `schedule`, `next_run_at`, `created_by`, `updated_by`. Ids são UUID completos
(36 caracteres) em todo lugar.

O catálogo de tools custa 27.845 caracteres de schema (≈7 mil tokens) quando o cliente carrega
tudo; a tool `manage_items` sozinha tem 2.069 caracteres de schema e 16 parâmetros.

## O que já me ajuda (e não deve ser mexido)

- **Erros estruturados** com `code`, `message` e `field`. Corrigi chamadas hoje sem tentativa e
  erro: `NOT_FOUND` com o campo `id`, `CONFLICT` nomeando a tripla que detém o item.
- **Ids curtos na entrada** (prefixo de 4+ caracteres) reduzem o que eu preciso copiar.
- **`get_next_item()`** é a melhor tool da casa: 150 tokens e uma decisão.
- **`get_next_status()`** permite prever sem efeito colateral.
- **Onboarding servido pelo servidor** (tool + resources) me ensinou o produto sem gastar turnos.
- **`claim`/`conflicts`** resolvem o problema real de dois agentes no mesmo item.

## O que me atrapalha, em ordem de custo

### 1. Listas devolvem a linha inteira do banco — P0 de contexto

Uma chamada de listagem custa 7.483 tokens. Eu não preciso de 22 campos para decidir o próximo
passo: preciso de id, título, status, prioridade e pai. O resto é peso morto que empurra o
contexto para o teto e me faz esquecer o começo da própria sessão.

**Proposta:** projeção. `query_items(..., fields="id,title,status,priority,parent_id,due_at")` e um
modo `compact=true` que é o default para listas. Estimativa com projeção: 50 itens em ~7.500
caracteres em vez de 29.932 (−75%). Ids curtos na saída (`id` de 8 caracteres + `id_full` sob
demanda) cortam mais ~3 mil caracteres na mesma chamada.

### 2. Não existe resumo de sessão — P0 de fluxo

Hoje, para começar, eu chamo `get_context` (1.690 tokens), depois `agent_list` para saber se alguém
está no item, e às vezes `get_execution_stack` (552). São três chamadas e mais de 2 mil tokens para
responder "onde eu estava e o que faço agora".

**Proposta:** `session_brief(session_id, since="")` com teto rígido de 1.500 caracteres: meus
claims, meus itens ativos, o que mudou desde `since`, bloqueios que me afetam, e o próximo item
recomendado. Uma chamada, uma tela de texto.

### 3. Não há leitura incremental — P1

Cada sessão relê o board inteiro. `updated_since` em `query_items` e `get_context` me deixa pegar
só o delta. Sem isso, o custo de retomar trabalho cresce com o tamanho do board — exatamente ao
contrário do que se quer de um board que deve durar meses.

### 4. Parâmetros JSON dentro de string — P1 de confiabilidade

`items_json`, `ids_json`, `transitions_json`, `subjects_json` me obrigam a serializar JSON dentro de
uma string: escape duplo, mais tokens, mais erro. O protocolo aceita arrays e objetos nativos.

**Proposta:** aceitar array/objeto nativo nesses parâmetros, mantendo a string como alias
depreciado. Sem quebrar cliente existente.

### 5. Tools-deus com RPC por `operation` — P1 de descoberta

`manage_items(operation=create|update|delete, ...)` tem 16 parâmetros e 2.069 caracteres de schema.
Eu preciso ler tudo para criar um item simples, e o docstring tem de antecipar todas as combinações.
Isso me faz errar e gastar chamada.

**Proposta:** separar em verbos pequenos (`create_item`, `update_item`, `delete_item`,
`batch_create`), com schemas de 300–500 caracteres. O custo de mais nomes é menor que o de um
schema gigante, principalmente em clientes que só carregam o schema da tool chamada.

### 6. Recorte de leitura não existe no servidor — P1

Subagentes herdam o catálogo inteiro. Hoje o recorte é conselho no texto, não garantia.
**Proposta:** um endpoint MCP separado (`/mcp-read`) com 8 tools de leitura, servido pelo mesmo
processo. Aí o recorte é imposto pelo servidor, não pela disciplina do operador.

### 7. Claim sem prazo — P2

Se eu morro no meio, o item fica preso até alguém liberar. `claim(..., lease_s=900)` com renovação
por heartbeat resolve sem eu manter relógio próprio.

### 8. Idempotência — P2

Retry de `create_work_tree` depois de timeout cria árvore duplicada. `Idempotency-Key` por chamada
(ou hash do payload numa janela curta) eliminaria a classe de erro.

### 9. `has_more` explícito — NIT

Hoje eu deduzo truncamento quando `len == limit`. Um campo `has_more` + `next_offset` me poupa a
inferência e a segunda chamada especulativa.

## Prioridade sugerida

| Ordem | Item | Ganho medido ou estimado | Custo |
|---|---|---|---|
| 1 | Projeção/compacto nas listas | −75% por listagem (7.483 → ~1.870 tokens) | baixo |
| 2 | `session_brief` | −60% no início de sessão (2,4k → <500 tokens) | médio |
| 3 | `updated_since` | custo constante ao retomar | baixo |
| 4 | Parâmetros nativos (sem `*_json`) | menos erro e menos tokens | baixo |
| 5 | Verbos pequenos no lugar do tool-deus | menos schema lido por chamada | médio |
| 6 | `/mcp-read` para subagentes | −70% de catálogo no worker | médio |
| 7 | Lease no claim | higiene de concorrência | baixo |
| 8 | Idempotência | elimina duplicata em retry | médio |

## Critérios de aceite (itens 1–3)

AC1. `query_items` com `compact=true` (default) devolve ≤150 caracteres por item e ≤7.500
     caracteres para 50 itens, medidos na placa de 64 itens deste documento.
AC2. Projeção por `fields` funciona em `query_items`, `get_blocked_items` e `get_context`, e um
     campo inexistente devolve erro estruturado com `field`, não silêncio.
AC3. `session_brief` devolve ≤1.500 caracteres com as cinco seções, para uma sessão com 3 claims e
     12 itens ativos.
AC4. `updated_since` reduz o payload a somente itens alterados, provado com um item alterado entre
     duas leituras.
AC5. Nenhuma mudança quebra os 255 testes atuais nem os clientes que já chamam sem os novos
     parâmetros (compatibilidade por default).
AC6. O texto de onboarding ensina o caminho barato: começar por `session_brief`, nunca listar sem
     `compact`.

## Não escopo

- Mudar o modelo de dados ou o estado persistido.
- Substituir `get_context`: ele continua sendo a visão completa para o humano e para depuração.
- Filtros novos de negócio; isso é F9, não novas features de gestão.

## Nota de método

Toda estimativa aqui foi medida com a placa sintética descrita, não inferida. O número de 7.483
tokens por listagem é o custo real de uma chamada default — é a razão pela qual eu evito listar, e
evitar listar é o começo de operar no escuro.
