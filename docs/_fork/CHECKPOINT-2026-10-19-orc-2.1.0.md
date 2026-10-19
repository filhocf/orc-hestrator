# Checkpoint — Orc 2.1.0 (19/out/2026, ~19:40)

Estado: **pronto para publicação, não publicado.** `main` = `4bfa89a`.

## O que está feito e verificado

| Item | Evidência |
|---|---|
| FEAT-0 eco `structuredContent` | em produção desde 2.0.1; `structuredContent=0` reconfirmado no fio |
| Caracterização do contrato de leitura | 15 testes, baseline sha256, guarda anti-regravação em CI |
| FEAT-1 `get_context(verbosity)` | compact 1.163 chars no board real (teto 1.500) |
| FEAT-1b sem N+1 | 125 → 12 queries (full), 115 → 2 de dependências; guarda de orçamento |
| FEAT-6b workspaces no banco | migração limpa no snapshot real, 1 workspace importado, 176 itens idênticos |
| FEAT-2 projeção/compact | `query_items(50)` 70.428 → 8.148 chars (−88,4%); item ≤165 |
| Migrations fail-fast + `user_version` | 5 testes, inclusive banco travado |
| Release: CHANGELOG, pin 2.1.0, `__version__` derivada | `2b6fb0b` |

Suíte: **334 passed**; ruff limpo; `TOOLS.md --check` verde.

## Teste a quente (obrigatório antes de gerar versão)

Receita usada, e a usar no 2.2.0:

```bash
# 1. snapshot read-only da produção (não toca o banco vivo)
ssh cfnarede.dev 'sqlite3 ~/.local/share/orc/tasks.db "VACUUM INTO /tmp/orc-prod-$(date +%Y%m%d_%H%M).db"'
# 2. trazer para o lab, junto do workspaces.json legado
scp cfnarede.dev:/tmp/orc-prod-*.db ~/lab/orc-hot/prod-snapshot.db
# 3. trabalhar numa CÓPIA e apontar ORC_DB para ela
cp ~/lab/orc-hot/prod-snapshot.db ~/lab/orc-hot/hot.db
ORC_DB=~/lab/orc-hot/hot.db uv run python ...   # mede, migra, compara
```

Resultado: migração `user_version 0→1`, `integrity ok`, 176 work items preservados
**idênticos**, E2E de fio via cliente MCP: `get_context` **139.009 → 1.210 bytes (−99,1%)**.

## O que o teste a quente corrigiu (a placa mentia)

1. `blocked` sem limite: 25 itens, 2.682 chars → compact estourava em 5.814 (teto 1.500).
2. Títulos reais de 94 chars → item compacto de 242 (teto 150).
3. `_json` com `ensure_ascii=True`: cada acento virava `\u00e7` (6 chars). **Ofensor invisível na placa.**

Correções: `ensure_ascii=False`; 3 itens por lista com `*_total` visíveis; título 50;
`id`/`parent_id` em 8 chars. Baseline regravado (encoding mudou o payload).

## Pendente para publicar (ordem)

1. **Site** (`site/index.html`, 203 linhas): menciona "31 tools" (correto). Falta
   seção sobre 2.1.0 — economicidade de contexto e os novos parâmetros opt-in.
2. **Tag `v2.1.0`** → dispara PyPI. Irreversível, exige "vai" explícito.
3. **Deploy VPS**: `uv tool install --upgrade 'orc-hestrator-server[ui]'` +
   `systemctl --user restart orc.service`.
4. **E2E pós-deploy** contra produção: `/health` = 2.1.0, migração no boot,
   e medir compact contra o full do mesmo board (baseline já registrado aqui).

## Dívidas abertas (não bloqueiam 2.1.0)

- `b8dd62e1` migrations — **resolvido** em `45506a5`; fechar no board.
- FEAT-2/B: `query_items` compact usa teto 165, não 150 do RFC (motivo no teste).
- Vocabulário divergente: `get_workspace_context` usa `minimal/standard/full`,
  `get_context` usa `compact/standard/full`. Padronizar em 2.2.0.
- `scripts/ops/session_cost.py` não existe no Orc (só no mms).
- Item `faketime` não instalado → teste de virada de data não executado.

## Próximo arco

2.2.0 / F9: FEAT-3 `get_next_item(compact)`, FEAT-4 parâmetros nativos sem
`*_json`, FEAT-5 `_row_to_dict` null-strip, recorte `/mcp-read` por perfil.
Regra nova: **testar a quente antes de gerar versão** — placa só como regressão rápida.
