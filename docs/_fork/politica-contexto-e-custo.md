# Política de contexto e custo — Hermes/DeepSeek (aplicada ao Orc)

> Origem: `~/git/mms/mms/docs/_fork/politica-contexto-e-custo.md`. Vale para
> sessões neste repo. Motivo: o histórico é reenviado a cada turno; em sessão
> longa, a maior parte do que se paga é **gestão**, não trabalho.

## Limiares

| nível | tokens estimados | ação obrigatória |
|---|---|---|
| ok | < 150 mil | seguir |
| ATENÇÃO | 150–300 mil | checkpoint no repo + no mms antes de continuar |
| CRÍTICO | > 300 mil | encerrar a sessão e reabrir a partir do checkpoint |

## Regras que reduzem custo na origem

1. **Delegar o pesado.** Subagente tem contexto isolado; volta só o resumo.
2. **Achado vai para o repo, não para o contexto.** Commit + uma linha.
3. **Não despejar saída de ferramenta** — filtrar no comando (`--json`, `grep`, `head`).
4. **Resposta curta por padrão.** Tabela e número, não narrativa.
5. **Sem releitura.** Se já li nesta sessão, uso o que li; para conferir, `grep` dirigido.
6. **Checkpoint** em `docs/_fork/` + `mms` antes de sessão nova.

## Medição

`chars / 3.5` (misto PT/EN). Serve para tendência e gatilho, não para fatura.

## Nota do Orc

O projeto **não** tem `scripts/ops/session_cost.py` (isso é do mms). Para o Orc, o
número vem do próprio Hermes ao fim de cada turno. Se o volume de sessões no Orc
justificar, portar o script é uma tarefa pequena — registrado como dívida.
