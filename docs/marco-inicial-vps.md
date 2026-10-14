# Marco inicial — erguer o produto X na VPS (PLANO, não execução)

> Plano do primeiro marco de implementação. **NÃO executar nesta sessão** (Claudio sem
> tempo hoje). Deixar pronto para a próxima. **Data:** 2026-10-14.
> **Base:** PRD-X.md, ARCHITECTURE-X.md, ADR-001..005, migration-analysis.md.

## Objetivo do marco

Produto X de pé na VPS, banco **zerado**, exposto com segurança combinada, com um 2º MCP
conectando as máquinas e **só o trabalho útil** migrado. Resultado: fonte única, 0
divergências, agentes operando contra o central.

## Pré-requisitos (antes de começar)

- [ ] Decidir o **código base**: o produto X evolui do `task-orchestrator-py` (mesmo repo,
      branch `feat/produto-x`) — incorporar o session-registry como `presence.py`/`claims.py`.
- [ ] Confirmar com Claudio a **máquina-base** da migração (provável DNBSCDC289).
- [ ] Confirmar critério de "útil" (migration-analysis §3) e desempate dos divergentes (§4).

## Fase A — Serviço na VPS (infra)

1. [ ] Branch `feat/produto-x` no task-orchestrator-py; incorporar presence+claims
       (ADR-002); `agent_id` per-request (ADR-005). Gate G0-G5.
2. [ ] Deploy na VPS via skill `vps-deploy`: uv tool + systemd user service. Porta interna
       dedicada (não colidir com memory :8000). Banco em `~/.local/share/task-orch/` **zerado**.
3. [ ] nginx: location `/taskorch` + TLS + basic auth → proxy `127.0.0.1:PORT` (ADR-004).
4. [ ] OAuth2 client_credentials no serviço (ADR-004). Gerar client_id/secret.
5. [ ] Smoke test: `curl` autenticado → serviço responde; MCP tools listam.
6. [ ] Backup: cron VACUUM INTO (padrão do hub de memória).

## Fase B — 2º MCP nas máquinas

7. [ ] Adicionar MCP `task-orch-vps` no mcp.json das 3 máquinas, apontando para
       `https://cfnarede.dev/taskorch` (StreamableHTTP) com credencial basic+OAuth2.
8. [ ] Injetar `X-Agent-ID` (persona) por máquina no 2º MCP (ADR-005).
9. [ ] Manter o MCP local antigo (`task-orchestrator`) **em paralelo** por ora (não remover
       até validar). Convenção: durante a transição, o VPS é a fonte; o local é read-only/legado.
10. [ ] Smoke test de cada máquina: registrar presença, criar item teste, ver cross-máquina.

## Fase C — Migração seletiva

11. [ ] Query de seleção (migration-analysis §3) contra a máquina-base → lista de IDs úteis
        (+ deps + notes + épicos-pai). Estimar volume (~100-150).
12. [ ] Export seletivo (export_graph filtrado ou SQL).
13. [ ] Import no serviço central (banco zerado).
14. [ ] Reconciliar ~17 regressões de status manualmente (apresentar ao Claudio).
15. [ ] Validar: contagem, árvore de arcos íntegra, zero órfãos, deps consistentes.

## Fase D — Corte e aposentadoria

16. [ ] E2E: agente opera 100% contra a VPS (criar/avançar/claim/presença). Zero banco local.
17. [ ] Repontar oficialmente: VPS vira a fonte. Bancos locais → backup read-only.
18. [ ] Aposentar `mcp-session-registry` (comunicar; presença agora é do task-orch).
19. [ ] Checkpoint + memória + atualizar steerings que citam task-orch local (startup-hook,
        work-management, tools-reference).

## Critérios de pronto do marco

- Serviço X na VPS, banco zerado, nginx+OAuth2, respondendo.
- 2º MCP conecta as 3 máquinas; presença funciona cross-máquina.
- Só o útil migrado; árvore de arcos íntegra; 0 divergências estruturais.
- Agente opera contra o central sem banco local.

## O que este marco NÃO inclui (fica para depois)

UI de gestão, eventos externos movendo itens, flow DAG, híbrido (Etapa 2), multi-tenant.
Tudo no PRD §6. Este marco é só a **fundação central + migração limpa**.

## Nota de nome

Produto segue como `task-orch` provisório. Decidir nome definitivo (Condutor/Reger/...)
antes de criar repo próprio OU assumir que evolui no mesmo repo. Não bloqueia o marco.
