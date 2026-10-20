# Checkpoint — Orc 2.2.0 publicada (20/out/2026, ~09:55)

## Estado

- Release **2.2.0 no ar**: PyPI `orc-hestrator-server 2.2.0` (wheel + sdist), tag
  `v2.2.0`, CI run `39423879210` success.
- **Produção (cfnarede.dev) roda 2.2.0**; `get_context` em 117.252 chars no board vivo.
- Board: release `484d3c7f` e gate `a7a5662f` em `done`; achado do import_graph
  (`eaf0e066`) fechado junto.
- Repo `main` limpo, `a5de451`.

## Números da release (board real, pareado 2.1.0 × 2.2.0, 183 itens)

| Caminho | 2.1.0 | 2.2.0 | Δ |
|---|---|---|---|
| `get_context` full | 140.294 | 120.112 | −14,4% |
| `query_items(50)` | 66.125 | 57.688 | −12,8% |
| Sessão típica (AC-D1) | 206.419 | 177.800 | **−13,86%** |
| `get_next_item(compact)` | 1.424 | 170 | −88,1% |

AC-D1 histórico: −11,28% (strip só na raiz) → corrigido para 11% → o fix do
`blocked_by` aninhado (achado do G5) devolveu 2,6 p.p. → critério de volta a 12%,
atendido. Tudo registrado na spec §5 (R-D1a/b/c, R-D4b, AC-D1).

## Decisões desta sessão que agora estão escritas

- `docs/CONVENTIONS.md` — idioma por artefato (EN para o que é público, PT-BR
  para spec interna), formato do changelog, medição com ambiente, gate como item
  de board.
- DEVELOPMENT-STANDARDS do CdIA: §8.0 (granularidade/orçamento), §8.4.2 (retomada
  diferencial), §8.4.3 (review adversarial), §8.8 (formato de prova), §8.9
  (enforcement), §9.0.2 (changelog registro × diário).
- Skills: `worker-dev-python` (stash proibido em árvore compartilhada; commit é
  decisão do briefing), `worker-architect` (guarda contra devolver `tool_calls`
  como texto).

## Pendências conhecidas (não bloqueiam)

1. `/orc/ui/arcs/<id>` responde "Página não encontrada" — o SPA expande o arco
   inline; rota de detalhe nunca existiu (pré-existente).
2. O sdist publicado carrega o changelog do 2.2.0 em PT; PyPI não aceita
   reupload. Correção vale do `main` para frente.
3. `uv pip install` do PyPI pode falhar por cache de índice velho — usar
   `--no-cache` antes de acusar a publicação.

## Como retomar

`git log --oneline -3`, board `get_context(workspace="orc")`, e a spec
`docs/specs/SPEC-evolucao-2.2.0.md` §5. Instrumentos de teste a quente em
`~/orc-hot/` (`measure.py`, `e2e_wire.py`, `ui_exercise.py`, `prod_check.py`,
snapshot `snap-orig.db`).

## Fechamento do dia (20/out, tarde)

- **2.2.1 em produção** (não publicado no PyPI): `/api/arcs` devolve só raízes com
  filhos; `/api/arcs/{id}` devolve `has_children`; ícone segue filiação
  (commits `fba52a0`, `ce09a64`).
- **`scripts/build_ui.sh`** (`dee5763`): fixa `--base=/orc/ui/` e
  `VITE_API_BASE=/orc/api`. Sem os dois: tela branca e login mudo. nginx serve
  `~/orc-ui/`; publish por `tar | ssh` (não há rsync na VPS).
- **Board**: `ARC: Orc` (13 filhos, releases 2.1.0/2.2.0 dentro), `ARC: mms`
  (Delta-sync 7, Harvest 6, Learning 9, VM 5), `ARC: QueryFlow` (7), `ARC: DAIA`.
  Convenção: arco = raiz com filho; profundidade máxima 4.
- **Aberto**: `c0397e9b` (ícone de folha é check-circle em tarefa aberta — achado
  do Claudio), títulos longos truncados, chip de progresso sem netos, tag
  `v2.2.1` + PyPI (depende de autorização), DOC-ORC (DOC-1 em `work`).
