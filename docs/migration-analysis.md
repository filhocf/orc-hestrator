# Análise de migração — task-orch hoje → produto X (serviço central VPS)

> Como passar do estado atual (2 serviços, SQLite local, sync quebrado) para o produto X
> (serviço central na VPS, banco zerado + migração seletiva). **Data:** 2026-10-14.
> **Base:** PRD-X.md, ARCHITECTURE-X.md, ADR-001..005.

## 1. Estado atual (medido 14/out, banco sirdata)

| Métrica | Valor | Leitura |
|---------|------:|---------|
| work_items | **802** | — |
| dependencies | 223 | — |
| notes | 206 | — |
| status=queue | 400 (50%) | muitos nunca serão feitos |
| status=done | 338 (42%) | histórico concluído |
| status=cancelled | 29 | lixo explícito |
| status=work | 21 | WIP inflado (deveria ser ~3-5) |
| status=blocked | 13 | — |
| **não tocados >90d** | **466 (58%)** | **o grosso do lixo** |
| tocados ≤7d | 102 | trabalho vivo real |
| tocados 7-30d | 158 | semi-ativo |

**Problemas estruturais a NÃO carregar para o produto novo:**
- **109 itens com status divergente** entre sirdata e DNBSCDC289 (sync union-only).
- WIP inflado (21 em work; muitos são épicos/guarda-chuva ou itens esquecidos).
- Projetos concluídos ainda como `queue` (ex: `roma-connect`, 41 itens — projeto encerrado).
- Dois sistemas separados (task-orch + session-registry) com estado próprio.

## 2. Princípio da migração: banco ZERADO + migração seletiva

O banco da VPS **nasce vazio**. **Não** fazemos dump-and-restore do banco atual — isso
carregaria 58% de lixo e os 109 divergentes. Migramos **só o útil**, resolvendo a
divergência no processo (é a oportunidade de limpar).

## 3. Critério de "útil" (o que migra)

Um item migra se satisfaz **qualquer** uma:

| Regra | Racional |
|-------|----------|
| `status ∈ {work, review, blocked}` | trabalho vivo ou travado — precisa continuar |
| `status=queue` **E** `updated_at ≤ 30d` **E** prioridade `high`/`critical` | fila relevante e recente |
| é **épico/arco pai** de algum item que migra | preserva a árvore (não órfãos) |
| `status=queue` com `due_at` futuro | compromisso datado |

**NÃO migra (fica no legado/backup):**
- `status ∈ {done, cancelled}` → histórico; preservado no backup do banco antigo, não no vivo.
- `status=queue` não tocado há >30d sem prioridade alta → fila morta (inclui roma-connect,
  itens de 2026-04/05 nunca iniciados).
- Itens de projeto concluído (ex: roma-connect) mesmo que queue.

**Estimativa grosseira:** dos 802, devem migrar ~**100-150** itens (os 102 ativos de ≤7d +
blocked/work + épicos-pai + fila high recente). ~650 ficam no legado. Confirmar com query
seca antes de executar.

## 4. Resolver os 109 divergentes DURANTE a migração

A migração seletiva **absorve** o problema dos 109: ao escolher o que migra, para cada
item divergente decide-se o estado correto **uma vez** (fonte única daí em diante). Regra
de desempate sugerida (a confirmar com Claudio):
- Para itens que migram: usar o estado de `updated_at` mais recente entre as máquinas
  (last-write real), **exceto** regressões suspeitas (`done→queue`/`done→work`) que vão
  para revisão manual (são ~17 casos, não 109).
- A maioria dos 109 é de itens que **não migram** (roma-connect queue→cancelled etc) →
  o problema evapora para esses.

## 5. Processo de migração (passos)

1. **Backup** do banco atual nas 3 máquinas (já há `.hot.db` timestamped em memory-backups).
2. **Snapshot de referência**: escolher a máquina com estado mais avançado como base de
   leitura (DNBSCDC289 fez a limpeza RER/Roma — provável base).
3. **Query de seleção**: rodar o critério §3 contra o banco base → lista de IDs a migrar.
4. **Export seletivo**: `export_graph` filtrado (ou SQL) só dos IDs selecionados + suas
   deps + notes + épicos-pai.
5. **Import no serviço central** (banco zerado da VPS) via a API do produto X.
6. **Reconciliar os ~17 casos de regressão** manualmente (done→queue/work) — apresentar
   ao Claudio.
7. **Validar**: contagem, árvore de arcos íntegra, nenhum órfão, deps consistentes.
8. **Repontar** os clientes MCP das 3 máquinas para o 2º MCP (`task-orch-vps`).
9. **Aposentar** bancos locais (viram backup/legado, read-only).

## 6. Migração do session-registry

O session-registry **não tem estado durável a migrar** (presença/claims são efêmeros,
reaped em 5min). Migração = **re-registro**: os agentes passam a registrar presença no
serviço central. Zero dado histórico a mover. O repo `mcp-session-registry` é aposentado
(ADR-002); comunicar consumidores.

## 7. Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Perder item útil na seleção | Backup completo preservado; critério peca por incluir (épico-pai, due futuro). Revisável. |
| Órfãos (filho migra, pai não) | Regra "épico-pai de item que migra sempre migra". Validação §5.7. |
| Regressão de status mal resolvida | ~17 casos a revisão manual, não automático. |
| Downtime na troca | Serviço novo sobe em paralelo; repontar MCP só após validar. Banco antigo intacto até confirmar. |

## 8. O que fica para DEPOIS da migração (não bloqueia o marco inicial)

- Higiene fina dos itens migrados (fechar WIP real, rebaixar épicos).
- UI, eventos, DAG, híbrido (PRD §6).
