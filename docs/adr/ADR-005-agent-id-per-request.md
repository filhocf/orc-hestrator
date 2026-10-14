# ADR-005 — Identidade de agente (`agent_id`) resolvida por requisição

**Data:** 2026-10-14 · **Status:** Aceito · **Decisores:** Claudio, Zero
**Correlato:** memory-service RFC #1285 (mesma decisão, já provada lá)

## Contexto

Com N agentes (Zero em 3 máquinas, T'Pol, Scotty, subagentes) conectando ao MESMO serviço
central via MCP StreamableHTTP, o serviço precisa saber **quem** fez cada operação (criou
item, reivindicou, avançou). Um `agent_id` global no serviço não distingue N agentes atrás
do mesmo socket. Mesmo problema que o memory-service enfrentou (RFC #1285): env global
falha quando N harnesses chegam a 1 servidor.

## Decisão

`agent_id` resolvido **por requisição**, com precedência:
1. arg explícito na tool (quando o agente declara)
2. **header/`_meta` per-request** (`X-Agent-ID`) — o modelo que escala para N:1
3. env `MCP_AGENT_ID` (válido só em deployment 1:1 stdio)
4. null (desconhecido)

Semântica do `agent_id` = **persona** (zero, tpol, scotty), não harness — alinhado à
decisão do memory-service.

## Razão

- Env global do serviço central não distingue autores (todos viram o mesmo). Header
  per-request é o único modelo que escala para N agentes num socket compartilhado.
- Já **provado** no memory-service (web API usa X-Agent-ID). Reusar a mesma mecânica.
- Habilita "quem está no quê" (ADR-002) e atribuição de autoria nas operações.

## Consequências

- ✅ Presença, claims e autoria de operações corretamente atribuídas por agente.
- ✅ Base para a UI de gestão mostrar o time (quem fez o quê).
- ⚠️ O 2º MCP de cada máquina/agente precisa injetar o header com a persona correta.
- ⚠️ Fallback null quando não configurado — operações anônimas possíveis (aceitável v0.1).

## Alternativas descartadas

- **Env global**: não distingue N agentes num socket. Descartado (lição do memory-service).
- **Só arg explícito**: nem todo harness deixa o agente controlar o arg. Insuficiente só.
