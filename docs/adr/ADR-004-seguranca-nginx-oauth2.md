# ADR-004 — Segurança: nginx (basic auth + TLS) + OAuth2 no serviço

**Data:** 2026-10-14 · **Status:** Aceito · **Decisores:** Claudio, Zero

## Contexto

Com o task-orch exposto na VPS (ADR-001), o serviço fica acessível pela internet. Precisa
de autenticação. O mesmo problema foi resolvido e validado no hub de memória
(memory-service) na mesma VPS.

## Decisão

Reutilizar o padrão provado do memory-service: **duas barreiras**.
1. **nginx na borda**: TLS + basic auth. Primeira barreira, bloqueia tráfego não
   autenticado antes de chegar ao serviço. Proxy para `127.0.0.1:PORT` (serviço nunca
   exposto direto).
2. **OAuth2 no serviço** (client_credentials): segunda barreira, autentica o cliente MCP.

## Razão

- É o padrão **já validado** no hub de memória (`cfnarede.dev/memory`) — zero invenção,
  risco conhecido.
- Defense-in-depth: mesmo que uma barreira falhe, a outra segura.
- OAuth2 client_credentials é adequado a cliente-máquina (agentes), sem fluxo interativo.

## Consequências

- ✅ Superfície exposta protegida por padrão conhecido e testado.
- ✅ Caminho claro para a instância corporativa: OAuth2 → SSO Keycloak/gov.br (troca só o
  provider, mantém a arquitetura).
- ⚠️ Agentes precisam de credencial (basic + client_id/secret) configurada no 2º MCP.
  Gerir segredos por máquina (fora do sync, como já fazemos no memory-service).

## Alternativas descartadas

- **Só OAuth2 (sem nginx basic)**: perde a 1ª barreira de borda. Descartado por
  defense-in-depth.
- **mTLS**: mais robusto mas mais complexo de operar para uso individual. Reavaliar na
  instância corporativa.
