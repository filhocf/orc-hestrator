# Checkpoint — sessão 31/out/2026 (sirdata, Zero MANAGER+CLIENT)

Sessão longa de evolução do Orc: 13 commits, release 2.2.1 no PyPI, serviço + UI
deployados na VPS, board reconciliado com as RFCs, e os incômodos de UI do Claudio
resolvidos e provados ao vivo.

## Entregue (tudo na main, pushado; HEAD 1e9d450)

### Release 2.2.1 — documentação de 1ª classe (arco DOC-ORC, fechado)
- **DOC-1** (`1663939`): seção `context_budget` em `onboarding.py` (EN/PT) — ensina
  `get_context(verbosity="compact")` (~331 tok) vs full (~34318), `get_next_item(compact)`,
  `query_items(compact)`.
- **DOC-4**: variante `claude` em `KNOWN_CLIENT_TYPES` (paridade com o mms).
- **DOC-2** (`62d3abd`+`bbe325d`): skill publicável `skills/orc/` (SKILL.md + 5 references).
  Review adversarial do tuvok pegou 1 P0 (precedência de `agent_id` inventava um passo
  "argument" que não existe no código) — corrigido.
- **DOC-3** (`0a5d85a`): README/llms.txt/BRING-YOUR-AGENT com a tabela de custo.
- **DOC-5** (`17a58c4`): medição — onboarding ≤786 tok/variante, todas < 1000.
- Tag `v2.2.1` → PyPI (publish.yml, trusted publishing, success). Serviço na VPS
  reinstalado com `[ui]` extra e reiniciado (2.2.1, healthy).

### FEAT-CLIENT — get_next_item ignora containers (`280048d`)
- `engine/queries.py`: `get_next_item` nunca devolve um container (item com filho
  não-terminal). Um arco esgotado (filhos todos terminais, arco ainda aberto) volta a
  ser oferecido para fechar. Review do tuvok (P1) levou à regra "filho NÃO-terminal".
- Provado ao vivo: antes devolvia o ARC `344b09cd`; agora devolve folhas/arcos esgotados.

### UI — 3 incômodos do Claudio resolvidos e provados ao vivo
- **Ícone de folha por status** (`9825702`): `Arcs.tsx` — folha mostra ícone do status
  (queue=radio_button_unchecked, work=timelapse, done=task_alt...), não mais check falso.
- **Sanfona dos arcos**: já existia no código; o incômodo era a UI antiga. Deploy de hoje
  resolveu (provado: expandir/recolher ARC: Orc).
- **Grafo fiel ao Stitch** (`e3cd3a2`, merge `1e9d450`): trocado Cytoscape (bolinhas) por
  **React Flow + dagre** com card custom no estilo Stitch (rounded-xl, id curto + chip de
  status + título + rodapé, raiz com ring, arestas com seta). Bundle menor (548 vs 693 kB).
- **LiveTeam / session-registry**: confirmado funcionando ponta-a-ponta (registro MCP →
  presença central → tela "Time ao vivo" mostrando sirdata/zero/sess-...).
- **Site** (`c9a8897`): comando do hero não quebra mais em duas linhas.

## Board reconciliado (ARC: Orc, no Orc central)
O board não contava a história real; trouxe as RFCs e o trabalho invisível para itens:
- **SUB-ARC RFC-001** (flow DAG editável) — a grande visão, 4 fases (0-3) do §8. Fase 0
  (schema flows + current_node) é o ponto de entrada. **NÃO iniciada — decisão de rumo
  pendente do Claudio.**
- **SUB-ARC RFC-002** (Bring Your Agent) — F3 (skill) done = `skills/orc/`; F2 (identidade
  ponta-a-ponta) provada hoje; F5/F6/F8 abertas.
- **SUB-ARC Débito de UI** — fechado (sanfona + LiveTeam + Graph).

## Estado dos artefatos
- Serviço VPS: `orc.service` 2.2.1, healthy, `[ui]` extra instalado.
- UI VPS (`~/orc-ui`): bundle novo com os cards do grafo + ícone por status.
- PyPI: `orc-hestrator-server 2.2.1`.

## Pendências (próxima sessão)
1. **Decisão de rumo da RFC-001**: começar a Fase 0 (flow DAG) ou manter como visão
   documentada? Maior decisão de produto em aberto.
2. RFC-002 F5 (injeção de contexto, opcional), F6 (uma semana de campo), F8 (i18n frontend).
3. Backlog: CI com fluxo de PR + tests-prove-fix (`8ac44d0b`); portability (`c04de1db`).
4. Nit logo 512px (`200c4342`): **bloqueado** — falta a arte original em SVG/≥512.

## Lição registrada (mistake note)
Deploy na VPS: `uv tool install 'orc-hestrator-server[ui]'` — SEM o `[ui]` o fastapi some e
o `orc-serve` entra em crash-loop ("requires the 'ui' extra"); `is-active` engana (activating).
Confirmar `/health` com uptime baixo depois.
