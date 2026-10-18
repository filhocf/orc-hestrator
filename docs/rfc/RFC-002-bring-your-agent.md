# RFC: Bring Your Agent — Orc como MCP de primeira classe

**Data**: 2026-10-18 (sirdata)
**Autor**: T'Pol (CLIENT e MANAGER), a pedido de Claudio
**Status**: PARCIALMENTE ENTREGUE — camadas L1 e L2b implementadas; F0, F1, F4 e F7 fechadas em 18/out; F2, F3, F5, F6 e F8 abertas
**Antecedente**: `docs/rfc/RFC-001-orquestracao-visual-colaborativa.md` (visão de produto) · `docs/BRING-YOUR-AGENT.md` (diagnóstico e mapa de trabalho)
**Localização canônica**: `docs/rfc/RFC-002-bring-your-agent.md`
**Insumos**: medições de 18/out no sirdata contra o hub de produção (`https://cfnarede.dev/orc`); conversa de 07:50 que definiu os quatro objetivos (avaliar como CLIENT, conectar como CLIENT, mapear como MANAGER, desenvolver delegando)

## 1. Problema

O Orc já é o board central do time, mas um agente que chega nele não sabe com quem
está falando, não sabe como se identificar e não tem receita de instalação. O agente
fica pleno apenas se alguém já lhe explicou o ciclo — o que não escala para "Zero em
três hosts e T'Pol em três máquinas".

Sob a ótica de CLIENT, o defeito é de contrato, não de funcionalidade: as tools estão
lá (31), o trabalho é real (162 itens vivos), e mesmo assim o agente que conecta não
consegue responder sozinho a três perguntas: quem é o servidor, quem sou eu nesta
chamada, e qual é o próximo passo correto.

## 2. Visão

Um agente recém-instalado executa o ciclo completo — ler contexto, pegar item,
avançar, registrar nota — sem que um humano precise explicar nada, e sem que exista
uma segunda fonte de verdade do trabalho.

Duas consequências diretas:

- **O Orc é a verdade única do trabalho.** Itens, arcos, dependências, claims,
  presença e autoria vivem só dele.
- **A fila local é efêmera.** O kanban interno do Hermes deixa de ser board e passa a
  ser projeção somente leitura, alimentada por pull no momento em que o item é pego do
  Orc. Espelhamento bidirecional é **rejeitado**: diverge em uma semana e recria o
  problema que o Orc nasceu para resolver.

## 3. O que foi medido (sirdata, 18/out/2026)

| Fato | Medida |
|---|---|
| Identidade do servidor | `initialize` reportava `version = 1.27.0` (versão do SDK MCP) contra `1.5.0` em `/health` — o agente não sabia com quem falava |
| Autodescrição | 7 prompts e zero resources; onboarding só em texto de tool |
| Catálogo de tools | 31 tools; 20.322 caracteres de schema (≈5,1k tokens) se injetados por inteiro |
| Custo do transporte | catálogo adiado do Hermes cobra nome + uma linha por turno e o schema só sob demanda; o CLI não cobra nada adiantado, mas sobe um processo por chamada e não devolve resultado estruturado — no agregado o MCP sai mais barato |
| Deploy | `uv run` recriou o `.venv` sem o extra `ui` e o serviço morreu com `ModuleNotFoundError: fastapi` — duas ocorrências independentes |
| Credencial de borda | conflito de credencial entre `mcp.json` do cliente e hub: 401 nas duas combinações tentadas |
| Deriva de cliente | o `autoApprove` do Kiro cita tools que não existem no 2.0.0 (`claim`, `release`, `agent_list`, `agent_heartbeat`, `complete_tree`, `manage_checkpoints`) |

## 4. Arquitetura proposta — quatro camadas

### L1 — Servidor que se explica

O servidor declara quem é e como se usa: `orc_onboarding(client_type, lang)` com
variantes `hermes`, `kiro`, `cli` e `generic`, resources por idioma, `serverInfo.name`
e `serverInfo.version` vindos do pacote publicado.

**Estado:** entregue. `name = "orc"`, versão de `importlib.metadata`, 6 resources
(3 base + 3 `pt-BR`), onboarding em inglês canônico e português.

### L2 — Instalação de primeira classe (Hermes)

Receita de conexão no formato que o cliente entende, mais uma skill `orc-board` que
ensina o ciclo. A skill é o que substitui a explicação humana.

**Estado:** parcial. A receita existe (README, docs/CONFIGURATION.md); a skill
`orc-board` **não** foi escrita.

### L2b — Recorte de tools (custo de contexto)

Não oferecer 31 tools a todo turno. O recorte mínimo para operar é
`get_context`, `get_next_item`, `query_items`, `manage_items`, `advance_item`,
`manage_notes`, `claim`, `release`.

**Estado:** medido e decidido; implementação depende do recorte por cliente
(`hermes mcp configure`).

### L3 — Identidade ponta a ponta

`X-Agent-ID` → presença → `created_by`/`updated_by`, com `identity_header` por perfil
no cliente. Sem isso, o board não distingue T'Pol de Zero nem de um humano.

**Estado:** parcial. O servidor aceita o header e grava autoria; a prova ponta a ponta
com `sirdata/tpol/...` visível na presença **não** foi feita.

### L4 — Injeção de contexto (fase 2)

Injetar o contexto do board no prompt do agente. Só depois de medir o custo por turno
e provar ganho — a mesma disciplina que descartou o uso do grafo por MCP quando o CLI
bastava.

**Estado:** não iniciada, por decisão.

## 5. Mapa de trabalho

| Fatia | Escopo | Critério de pronto | Status |
|---|---|---|---|
| F0 | Auth do Orc em produção: credencial de borda, basic-via-header vs bearer, validar `/orc/mcp` de fora da VPS | `curl` autenticado devolve `tools/list` | **fechada 18/out** — handshake real com `orc` 2.0.0 e 31 tools |
| F1 | `orc_onboarding` + resources + `serverInfo.version` | tool chamada nos três `client_type`; `initialize` reporta a versão do pacote | **fechada** — entregue na leva anterior, versão corrigida em 2.0.0 |
| F2 | Identidade ponta a ponta | sessão aparece como `sirdata/tpol/...` e item criado com `created_by=tpol` | aberta |
| F3 | Receita + skill `orc-board` + recorte de tools | agente novo executa o ciclo só com a skill | aberta |
| F4 | Guarda de deploy (`uv sync --extra ui`) | falha explícita se `fastapi` ausente | **fechada** — `orc-serve` sai com exit 2 e mensagem que nomeia o extra |
| F5 | (opcional) injeção de contexto | custo medido por turno e justificado | aberta, opcional |
| F6 | Campo: uma semana usando o Orc como board real | relatório de atrito e decisão sobre desativar o kanban interno | aberta |
| F7 | Renomeação para `orc-hestrator-server` 2.0.0 e publicação | testes verdes, artefato instalável, publicado | **fechada 18/out** — ver `docs/specs/SPEC-rename-orc-hestrator.md` |
| F8 | i18n do produto (backend + frontend) | inglês canônico e pt-BR, troca de idioma no E2E | aberta |

## 6. Decisões pendentes de Claudio

1. Confirmar a fila efêmera como decisão de arquitetura (ADR própria): Orc é a verdade,
   kanban interno é projeção somente leitura.
2. Autorizar o recorte de tools para o perfil da T'Pol (L2b) — reduz schema por turno.
3. Decidir se a skill `orc-board` é escrita agora (F3) ou depois do campo de uma semana (F6).

## 7. Referências

- `docs/BRING-YOUR-AGENT.md` — diagnóstico, fricções medidas e mapa original
- `docs/specs/SPEC-bring-your-agent-onboarding.md` — spec da F1
- `docs/specs/SPEC-rename-orc-hestrator.md` — F7, com o diário de gate completo
- `docs/adr/ADR-006-rename-orc-hestrator.md`, `docs/adr/ADR-007-transport-by-entry-point.md`
- `docs/rfc/RFC-001-orquestracao-visual-colaborativa.md` — visão de produto
