# Bring Your Agent — Orc como MCP de primeira classe

Proposta de integração do Orc (task-orchestrator central) com agentes Hermes.
Status: proposta em avaliação (não aprovada). Autor: T'Pol, como CLIENT do Orc e MANAGER da entrega.

**Registro canônico de decisão:** `docs/rfc/RFC-002-bring-your-agent.md` (18/out/2026). Este
documento permanece como diagnóstico — medições, fricções e mapa de trabalho; o RFC é a peça que
carrega a proposta e o estado de cada fatia.

## Problema

O Hermes tem board interno, mas ele vive no `state.db` de UMA máquina. Consequências quando o
operador ou o agente troca de máquina, quando há mais de um agente (Zero em 3 hosts, T'Pol em 3
máquinas) ou quando o time cresce:

- o trabalho não acompanha o agente;
- dois agentes podem pegar o mesmo item sem saber;
- não existe presença cross-machine nem atribuição de autoria;
- o histórico de decisão fica preso a um host.

O Orc existe exatamente para isso: fonte única, presença central, claims e grafo de trabalho.

## O que foi medido (sirdata, 18/out/2026)

Servidor local (`127.0.0.1:3211`, banco limpo, commit `10d5848`), cliente MCP oficial:

| Item | Valor |
|------|-------|
| `initialize` | ok, protocolo streamable-http |
| Tools | 30 |
| Custo de schema | 27.845 chars ≈ 7,0k tokens por conexão |
| Prompts | 7 (`work_summary`, `create_item_from_context`, `quick_start`, `status_progression`, `dependency_manager`, `batch_complete`, `session_start`) |
| Resources | 0 |
| `serverInfo.version` | `1.27.0` (versão do SDK MCP, não do produto) |
| `/health` version | `2.0.0` |
| Fluxo real | `get_context`, `manage_items(create)`, `agent_register`, `agent_list` funcionaram |
| Erro de argumento | devolve `{"error":{code,message,field}}` — bom para o agente se corrigir |

### Fricções encontradas

1. **Credencial de produção não autentica.** `GET https://cfnarede.dev/orc/` com o par
   documentado (`orc` + senha em `~/dtp/ai-configs/.kiro/settings/mcp.json`) devolve **401**,
   realm `Orc Hub`. `/orc/mcp` idem. `/orc/health` responde 200 sem auth. Consequência: a entrada
   `orc-vps` do Kiro também está quebrada hoje, não só o Hermes. Bloqueador de qualquer
   bring-your-agent.
2. **O Hermes não consome `initialize.instructions`.** Verificado no código do cliente MCP do
   Hermes: as instruções do servidor não entram no contexto do modelo. Portanto "instalar e sair
   usando" NÃO acontece por si — o servidor precisa ensinar por tool/skill.
3. **Prompts não são injetados.** O Hermes expõe `list_prompts`/`get_prompt` como tools utilitárias
   (é o que se vê em `mcp__mms__*`). Só são usados se o agente souber que existem.
4. **Identidade se perde sem header.** `agent_register` não aceita `agent_id` como argumento; a
   identidade vem de `X-Agent-ID` (ADR-005). Na prova: sessão registrada como
   `sirdata/(anon)/sess-71d97fff` e item criado com `created_by: null`. O Hermes tem o encaixe
   exato: `identity_header: {name: X-Agent-ID, value_from: profile}`.
5. **URL com credencial embutida não é o caminho no Hermes.** O padrão do Kiro
   (`https://user:pass@host/...`) não encontra tratamento de *userinfo* no transporte HTTP do
   Hermes; o suporte é `--auth header` / `headers` com interpolação `${VAR}`.
6. **Descoberta frágil de parâmetros.** `create_work_tree` exige `root_title`; um agente que deduz
   `root: {...}` erra. O schema resolve, mas mostra que os nomes precisam de guia explícito.
7. **`uv run` sem `--extra ui` derruba o serviço.** Reproduzido: `uv run` recriou o `.venv` sem
   `fastapi` e o processo morreu com `ModuleNotFoundError: fastapi`. É o mesmo tropeço já registrado
   no CHANGELOG; precisa de guarda no deploy.

## Arquitetura proposta — quatro camadas

Espelha o que funcionou no mms (servidor que ensina + instalação de primeira classe + skill).

### L1 — Servidor que se explica

- Tool `orc_onboarding(client_type="hermes"|"kiro"|"cli")` devolvendo: modelo mental (item, arco,
  status, gates), o ciclo de sessão obrigatório, os 10 verbos que importam e os antipadrões
  (não criar item duplicado; sempre `claim` antes de trabalhar).
- `instructions` do FastMCP reescritas e curtas (hoje são 3 linhas corretas, mas invisíveis ao Hermes).
- Resources (hoje zero): `orc://onboarding`, `orc://workflow`, `orc://glossary`. Servem para
  qualquer cliente MCP, não só o Hermes.
- Corrigir `serverInfo.version` (passar a versão do pacote) para o agente saber com quem fala.

### L2 — Instalação de primeira classe (Hermes)

```yaml
mcp_servers:
  orc:
    url: https://cfnarede.dev/orc/mcp
    headers:
      Authorization: Basic ${ORC_BASIC}
    identity_header: {name: X-Agent-ID, value_from: profile}
    tools: <recorte>       # ver L2b
```

- `value_from: profile` faz o `agent_id` ser o nome do perfil Hermes (tpol, zero...), sem
  configuração por máquina.
- Segredo em env do perfil, nunca em arquivo versionado.

### L2b — Recorte de tools (custo de contexto)

7k tokens por conexão é aceitável para o agente principal e caro para subagente. Recorte proposto:

- `nucleo` (12): `get_context`, `get_next_item`, `query_items`, `manage_items`, `advance_item`,
  `manage_notes`, `query_notes`, `create_work_tree`, `agent_register`, `agent_heartbeat`,
  `agent_end`, `claim`.
- `leitura` (8, para subagentes): `get_context`, `get_next_item`, `query_items`, `query_notes`,
  `query_dependencies`, `get_blocked_items`, `agent_list`, `conflicts`.
- `completo` (30): operação e manutenção.

### L3 — Skill Hermes `orc-board`

Protocolo de sessão, no mesmo espírito de `memoria-mcp-primario`:

- início: `agent_register` (reusar `session_id`), `get_context`, `claim` do item escolhido;
- durante: `advance_item` nos gates, `manage_notes` para decisão e evidência, `agent_heartbeat`;
- fim: `agent_end` (libera claims) e registro do resultado no mms.
- antipadrões explícitos: não criar item sem buscar antes; não trabalhar sem claim; não usar o
  board como diário.

### L4 — Injeção de contexto (fase 2, medir antes)

Hook `pre_llm_call` (o perfil já usa `context_budget.py`) que injeta um resumo de 3 linhas do
board. Só depois de medir o custo: `get_context` completo pode ser grande. Não fazer agora.

## Mapa de trabalho

| Fatia | Escopo | Critério de aceite |
|-------|--------|--------------------|
| F0 | Auth do Orc em produção: confirmar/rotacionar credencial, decidir basic-via-header vs bearer, validar `/orc/mcp` de fora da VPS | `curl` autenticado devolve `tools/list` com 30 tools; entrada `orc-vps` do Kiro volta a funcionar |
| F1 | `orc_onboarding` + resources + `serverInfo.version` | teste automatizado chamando a tool nos 3 `client_type`; `initialize` reporta versão do pacote |
| F2 | Identidade ponta a ponta (`X-Agent-ID` → presença → `created_by`) com Hermes `identity_header: profile` | sessão de teste aparece como `sirdata/tpol/...` e item criado com `created_by=tpol` |
| F3 | Receita de instalação + skill `orc-board` + recortes de tools | agente novo, sem contexto prévio, executa o ciclo completo seguindo só a skill |
| F4 | Guarda de deploy (`uv sync --extra ui` obrigatório) e doc | restart limpo a partir de clone; falha explícita se `fastapi` ausente |
| F5 | (opcional) hook de injeção de contexto | custo medido por turno e justificado |
| F6 | Campo: uma semana usando o Orc como board real, com Zero e T'Pol | relatório de atrito e decisão sobre desativar o kanban interno |
| F7 | Renomeação para `orc-hestrator-server` 2.0.0 (dist, comandos, env, servidor, TOOLS.md gerado) | `docs/specs/SPEC-rename-orc-hestrator.md` — ADR-006 |
| F8 | i18n do produto: catálogo no backend, react-i18next no frontend, extrator de strings | inglês canônico e pt-BR; troca de idioma no E2E |

Gates: SDD (spec) → RED (testes) → GREEN (implementação) → review independente → validação.
Delegação: Zero (implementação backend), Scotty (VPS/ops e deploy), subagentes para review
independente. Nenhuma fatia vai a produção sem review que tente quebrá-la.

## Decisões pendentes de Claudio

1. Hierarquia de board: Orc como fonte única do trabalho cross-machine e kanban interno do Hermes
   apenas como fila local (recomendado), ou tentar sincronizar os dois (custo alto, duas verdades).
2. Auth: manter basic auth na borda e consumir por header (menor atrito), ou ligar `MCP_OAUTH_ENABLED`
   com token pré-compartilhado por agente (melhor trilha para SSO futuro).
3. Escopo da v1: F0–F4 (recomendado) ou começar só por F0–F1.
