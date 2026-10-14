# ADR-001 — Serviço central na VPS (fonte única) em vez de banco local + sync

**Data:** 2026-10-14 · **Status:** Aceito · **Decisores:** Claudio (owner), Zero (agente)

## Contexto

O task-orchestrator-py usa SQLite single-file sincronizado por arquivo (OneDrive/Insync)
entre 3 máquinas. O PRD original listava "sync entre máquinas" como **fora de escopo**
("resolvido pelo Insync no nível de arquivo"). Essa premissa falhou: sync de arquivo de
SQLite com duas máquinas editando em paralelo **não reconcilia estado** — só sobrescreve
(last-file-wins). Medição 14/out: **109 itens com status divergente** entre sirdata e
DNBSCDC289. O operador (humano e agente) perde a confiança no board.

## Decisão

O task-orch passa a rodar como **serviço central na VPS cfnarede.dev**. As máquinas
**não têm mais banco local** — todas leem/escrevem o mesmo banco via MCP StreamableHTTP.
Fonte única de verdade.

## Razão

"Banco local + sync" é um problema de **consistência distribuída** (difícil, foi o que
quebrou). "Um serviço, todos consumindo" é **cliente-servidor** (resolvido há décadas).
Trocamos o problema difícil pelo fácil. O blueprint já é provado: o hub de memória
(memory-service) roda exatamente assim na mesma VPS.

## Consequências

- ✅ Os 109 divergentes deixam de existir — não há cópias para divergir.
- ✅ Menos fricção: zero tempo gasto reconciliando por sessão.
- ⚠️ **Trade-off aceito:** sem rede/VPS = board indisponível naquela máquina. Hoje, com
  banco local, há board offline. Aceito porque cobre ~95% do uso real (quase sempre há
  rede). Mitigação futura: ADR-003 (híbrido, Etapa 2).
- ⚠️ Dependência operacional da VPS (uptime, backup). Mitigado por VACUUM INTO periódico.

## Alternativas descartadas

- **Delta-sync no task-orch** (event-log reconciliando cópias locais, como o
  memory-service): resolveria o offline, mas é complexo e desnecessário se há fonte
  única. Ver ADR-003.
- **Continuar com sync de arquivo**: é a causa-raiz. Descartado.
- **Adotar ferramenta OSS pronta**: ver matriz `docs/rfc/matriz-decisao-oss-2026-10-14.md`
  — nenhuma cobre nosso core (arcos/gates/memory bridge) com maturidade. Descartado.
