# Medição DOC-5 — custo de onboarding por cliente (31/out/2026)

Fecha o arco DOC-ORC (release 2.2.1). AC: número medido por cliente; nenhum
cliente acima de 1.000 tokens na abertura.

## Ambiente

- Host: sirdata. Branch `feat/doc-onboarding` (worktree `orc-wt-doc1`), após os
  commits DOC-1/DOC-4 (`1663939`), DOC-3 (`0a5d85a`), DOC-2 (`62d3abd`+`bbe325d`).
- Métrica do projeto: `chars / 3.5` (misto PT/EN). Tendência e gatilho, não fatura.
- Comando:
  ```
  uv run python -c "from task_orchestrator.onboarding import build_onboarding_text; ..."
  ```

## Resultado — custo da tool `orc_onboarding` por variante × idioma

| client_type | lang | chars | ~tokens | teto 1000 |
|---|---|---|---|---|
| hermes | en | 2717 | 776 | OK |
| hermes | pt-BR | 2751 | 786 | OK |
| kiro | en | 2460 | 703 | OK |
| kiro | pt-BR | 2491 | 712 | OK |
| cli | en | 2606 | 745 | OK |
| cli | pt-BR | 2625 | 750 | OK |
| claude | en | 2634 | 753 | OK |
| claude | pt-BR | 2678 | 765 | OK |
| generic | en | 2489 | 711 | OK |
| generic | pt-BR | 2499 | 714 | OK |

**Máximo: 786 tokens (hermes/pt-BR). Nenhuma variante acima de 1.000.** AC atendida.

## O que mudou com o arco DOC-ORC

Antes (medido 20/out, PLANO-documentacao): o onboarding tinha ZERO menções a
`verbosity`/`compact` e ensinava o caminho de ~34.318 tokens (get_context full).
Abertura de sessão do Zero custava ~34.725 tokens.

Depois:
- O onboarding (≤786 tok/variante) agora inclui a seção `context_budget` que
  ensina `get_context(verbosity="compact")` (~331 tok) em vez do full (~34.318),
  `get_next_item(compact=True)` (~49 tok) e `query_items(compact=True)`.
- O custo de abertura informada passou a ser: onboarding (~780 tok) +
  get_context(compact) (~331 tok) ≈ **1.1k tok**, contra ~34.7k do caminho antigo
  — redução de ~97%.
- Variante `claude` adicionada (paridade com o mms). Skill publicável em
  `skills/orc/` (EN, sem paths de máquina). Docs humanas (README/llms.txt/
  BRING-YOUR-AGENT) com a tabela de custo.

## Fatias do arco (todas done)

- DOC-1: `context_budget` no onboarding (EN/PT). Gate RED→GREEN, 380 testes.
- DOC-2: skill publicável `skills/orc/` + 5 references. Review adversarial
  (tuvok) pegou 1 P0 (precedência de agent_id) corrigido.
- DOC-3: README/llms.txt/BRING-YOUR-AGENT com custo explícito.
- DOC-4: variante `claude` (fechada junto com DOC-1).
- DOC-5: esta medição.

## Pendente para fechar a release 2.2.1

- Merge da branch `feat/doc-onboarding` na `main`.
- CHANGELOG: seção 2.2.1 (docs + onboarding string).
- Tag `v2.2.1` + PyPI: **só com "vai" explícito do Claudio** (tag dispara publish,
  irreversível). O serviço na VPS já roda 2.2.1 (UI/arcs); esta release é a de
  documentação.
