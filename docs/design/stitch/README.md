# Orc[hestrator] — Design (Stitch)

Material de design gerado no Stitch (Google) a partir do briefing
`orc-ui-stitch-briefing.md`, entregue 2026-10-16. Fonte de referência visual para
implementar o **frontend desacoplado** que consome a API REST do Orc (`/api`, ver
`docs/specs/SPEC-http-api.md`). **São mockups HTML/Tailwind + PNGs — não é o código de
produção.** O frontend real será implementado a partir destes (framework a decidir;
provável React/Vite consumindo a API).

## Identidade

- **Nome/marca:** Orc[hestrator] — orc amigável de capacete de obra (ver
  `orc_hestrator_mascote_oficial/screen.png`). Divertido, não corporativo.
- **Design system canônico:** `orchestrator_control_hub/DESIGN.md` — paleta, tipografia,
  rounded, spacing (tokens). Tema escuro azul-marinho (`#031427`) + accent âmbar
  (`#ffc174`/`#f59e0b`, o amarelo-segurança do capacete). Fontes: Plus Jakarta Sans
  (headings) + Inter (corpo).

## Telas (cada pasta: `code.html` mockup + `screen.png` preview)

| Pasta | Tela |
|---|---|
| `vis_o_geral_orc_hestrator` | Visão geral / dashboard (cards-resumo + Time ao vivo + Atividade recente) |
| `time_ao_vivo_orc_hestrator_1/2/3` | Time ao vivo (presença) — 3 variantes a comparar |
| `board_kanban_orc_hestrator` | Board Kanban (fila/trabalhando/revisão/concluído, swimlanes) |
| `rvore_de_arcos_orc_hestrator` | Árvore de arcos (hierarquia épicos→sub→tarefas) |
| `grafo_dag_orc_hestrator` | Grafo DAG (dependências/fluxo) |
| `detalhe_da_tarefa_orc_hestrator` | Detalhe da tarefa (autoria, claim, deps, notas) |
| `administra_o_rbac_orc_hestrator` | Administração / RBAC (usuários, papéis) |
| `perfil_e_configura_es_orc_hestrator` | Perfil e configurações (tema, idioma) |
| `login_orc_hestrator` | Login (+ SSO futuro) |
| `orc_hestrator_mascote_oficial` | Mascote oficial (logo) |

## Alinhamento com o backend (confirmado)

O dashboard renderiza EXATAMENTE o modelo que o backend já implementa:
- **Tripla host/agente/sessão** na presença (ex. `DNBSCDC289 / zero / session-a1b2`,
  cliente `kiro-cli`/`kiro-ide`/`humano`) → tabela `sessions` (session-registry 1.4.0).
- **Claims** ("reivindicou a tarefa #204") → `claims` + `get_claim_for`.
- **Autoria** ("claudio aprovou", "sentinel completou") → `created_by`/`updated_by` (agent_id).
- **Contadores por estado, bloqueios, tempo de ciclo** → `get_context` / `get_metrics`.
- Contrato de texto pt-BR do briefing respeitado nos rótulos.

## Próximos passos (implementação do frontend)

1. Escolher o que colher (Claudio) — quais telas/variantes entram no MVP.
2. Escolher stack do frontend (React/Vite provável) consumindo `/api`.
3. Extrair os tokens do DESIGN.md para o tema (claro/escuro).
4. Implementar tela a tela, ligando aos endpoints REST. Prova visual com o Claudio.
