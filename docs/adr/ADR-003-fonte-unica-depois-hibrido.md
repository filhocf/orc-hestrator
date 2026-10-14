# ADR-003 — Fonte única (Etapa 1) → híbrido (Etapa 2) por etapas; sem delta-sync

**Data:** 2026-10-14 · **Status:** Aceito · **Decisores:** Claudio, Zero

## Contexto

ADR-001 decidiu serviço central na VPS. Surge a questão de disponibilidade offline: hoje
o banco local garante board mesmo sem rede. Há duas arquiteturas que preservariam offline:
- **Delta-sync**: banco local + event-log reconcilia cópias (modelo do memory-service).
- **Híbrido**: primary local + secondary HTTP (hub), também do memory-service.

Essas duas são **alternativas, não complementares**: com fonte única não há o que
sincronizar.

## Decisão

Implementar por **etapas**:
- **Etapa 1 (v0.1): fonte única na VPS.** Sem banco local. Mais simples, mata os 109
  divergentes imediatamente.
- **Etapa 2 (futuro): híbrido** (primary local + secondary hub, modelo memory-service).
  Offline-capable. Construir **apenas depois** da Etapa 1 de pé e **se** a
  indisponibilidade offline incomodar na prática (medir antes de pagar o custo).

**Não construir delta-sync** para o task-orch.

## Razão

- Fonte única elimina a necessidade de sincronização por definição — construir delta-sync
  seria resolver um problema que a Etapa 1 já apagou.
- Etapa 1 cobre ~95% do uso real (quase sempre há rede). Pagar a complexidade do híbrido
  antes de medir a dor é otimização prematura.
- Por etapas respeita "resolver 1 coisa bem": provar o central, medir, só então evoluir.

## Consequências

- ✅ v0.1 enxuta: cliente-servidor puro, sem camada de reconciliação.
- ✅ Caminho de evolução claro (híbrido) sem reescrever — o modelo já existe no
  memory-service para copiar.
- ⚠️ Até a Etapa 2, sem rede = sem board. Risco monitorado; se virar dor real, dispara a
  Etapa 2.

## Alternativas descartadas

- **Delta-sync direto**: complexidade alta para um problema que a fonte única resolve.
- **Híbrido já no v0.1**: otimização prematura; não medimos ainda se o offline dói.
