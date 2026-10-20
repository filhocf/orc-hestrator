# Plano — documentação de 1ª classe do Orc (20/out/2026)

## Problema

O Orc tem docs humanas razoáveis (README 272 linhas, ARCHITECTURE, CONFIGURATION,
WORKSPACE-GUIDE, TOOLS.md gerado, site) e um `orc_onboarding` de 476 linhas com
variantes por cliente. Mas:

- `orc_onboarding`: **zero** menções a `verbosity`/`compact` → o método ensina o
  caminho de 34.318 tokens, não o de 331.
- `BRING-YOUR-AGENT.md` e `llms.txt`: idem, zero.
- A skill que sabe operar o Orc (`orc-work-item-management`) é **privada**, em
  `~/.hermes/skills` — não viaja com o produto.
- Não há receita de instalação por cliente (Kiro, Hermes, Claude).

Consequência medida: abertura de sessão do Zero custava ~34.725 tokens até hoje.

## Princípio

Três audiências, três artefatos, um só conteúdo:

| Audiência | Artefato | Onde vive | Idioma |
|---|---|---|---|
| Humano | README, docs/, site | repo | **EN** |
| Agente — método | tool `orc_onboarding` | servidor (MCP) | **EN** (variante PT-BR por `lang`) |
| Agente — operação | skill `orc` | **repo** (distribuível) | **EN** |

Specs, planos e comentários internos: **PT-BR** (Claudio acompanha). Artefato
publicado: **EN**.

## Fatias

### DOC-1 — Onboarding v2 (`orc_onboarding`)
Custo primeiro: abrir com a tabela de tokens (full 34.318 × compact 331 ×
`get_next_item` 49) e a regra "leitura começa compacta, `full` exige motivo".
Receitas por cliente: `hermes`, `kiro`, `claude`, `cli`, `generic`. Inclui
troubleshooting (401 de proxy, `--db`, transporte stdio × streamable-http).
Arquivo: `src/task_orchestrator/onboarding.py`. AC: `orc_onboarding` menciona
`verbosity`/`compact` nas variantes e o texto EN/PT não divergem em conteúdo.

### DOC-2 — Skill publicável (`skills/orc/` no repo)
`SKILL.md` (EN) + `references/`: mapa de tools, gating de notas, economia de
payload, troubleshooting, receitas. Instalação documentada para Hermes e Kiro.
Base: a skill privada `orc-work-item-management`, reescrita em EN e sem
referência a máquina do Claudio. AC: um agente sem contexto instala a skill e
completa um ciclo criar→avançar→nota→consultar sem pedir ajuda.

### DOC-3 — Docs humanas com custo explícito
`llms.txt`, `BRING-YOUR-AGENT.md` e README ganham a tabela de custo e o
compact-first; site `/what it costs` alinhado ao número medido. AC: os três
arquivos citam `verbosity`/`compact` e a regra de orçamento.

### DOC-4 — Variante `claude` (paridade com o mms)
O mms já serve `claude-code` em `get_onboarding_guide`; o Orc só tem hermes/kiro/cli.
Copiar o padrão de receita (config do cliente, transporte, headers de identidade,
primeira chamada). AC: `orc_onboarding(client_type="claude")` devolve receita
completa, não `generic`.

### DOC-5 — Medição e gate
Custo de abertura por cliente antes/depois, com comando e ambiente; teste de
aderência (agente novo, com só a skill, mede o próprio consumo). AC: número
medido por cliente no relatório; nenhum cliente acima de 1.000 tokens na abertura.

## Ordem

DOC-1 e DOC-3 em paralelo (arquivos disjuntos, ambos textuais);
DOC-2 em paralelo (diretório novo, não colide);
DOC-4 depois de DOC-1 (mesmo arquivo);
DOC-5 por último (mede o conjunto).

## Gate

G0–G6 do DEVELOPMENT-STANDARDS §8, sem atalho: DOC-1/DOC-4 tocam código de
servidor (tool) → RED no contrato do texto (asserção sobre conteúdo obrigatório
por variante), GREEN, review adversarial (tuvok) e teste a quente com
`orc_onboarding` real por cliente. DOC-2/DOC-3 são docs: exceção de delegação
(§8.4), com revisão adversarial mesmo assim — doc errado é pior que código errado,
porque ensina o erro.

Release: 2.2.1 (MINOR não é necessário — é documentação + tool string; PATCH).
Tag e PyPI só com autorização do Claudio.

## Fora de escopo

- Mudar o default de `get_context` para `standard` (é 2.3.0/MAJOR, decisão
  separada; ver CONVENTIONS.md e §9.1).
- Traduzir docs publicadas para PT-BR (internacional = EN).
- Clientes além de Kiro, Hermes, Claude e `generic`.
