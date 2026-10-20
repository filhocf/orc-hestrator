# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.2.0] — em desenvolvimento

### Added
- **`get_next_item(compact=true)`**: devolve só `id` (8 chars), `title` (≤60),
  `status`, `priority`, `due_at` e **`reason`** — por que aquele item venceu a
  fila (`in progress`, `overdue` ou `priority:<nível>`). Medido: ~300 → ~44
  tokens (−85%); no board real (20/out): 1.424 → **170 chars** (−88,1%).
  Sem `compact`, a resposta é a mesma de 2.1.0.
- **Parâmetros nativos nas tools de lote.** `items_json`, `ids_json`,
  `transitions_json`, `children_json`, `deps_json`, `subjects_json` e `data_json`
  aceitam array/objeto direto, sem serializar e escapar. A string JSON continua
  aceita. Valor inválido devolve erro estruturado **nomeando o parâmetro** e o
  tipo esperado, em vez de `JSONDecodeError` cru.

### Changed
- **Payloads de lista não enviam mais chaves nulas (fatia D).** `query_items`,
  `get_blocked_items`, `get_context` (`active`, `recent`, `stale`) e
  `get_next_item` deixam de mandar chave cujo valor seja `NULL` — a chave
  simplesmente não aparece, em vez de vir `null`. As chaves **estruturais**
  (`id`, `title`, `status`, `priority`, `created_at`, `created_by`,
  `updated_at`) permanecem sempre presentes, mesmo nulas: `created_by` é
  contrato fixado por `test_http_api` desde a 1.5.0, e um consumidor que perde a
  proveniência não distingue item de stub. `summary` e `description` também
  ficam (o schema dá default `''`, e string vazia é valor). `get_item` mantém
  **todas** as chaves — quem precisa distinguir "ausente" de "nulo" continua
  lendo o item inteiro. Medido no board real, pareado na mesma cópia (183 itens):
  `get_context` 140.294 → 125.452 chars e `query_items(50)` 66.125 → 57.688 —
  **−11,28% na sessão típica** (23.279 chars ≈ 6.650 tokens por sessão). A
  bancada sintética dá −18,3% porque cria itens vazios; o board real tem mais
  campos preenchidos, logo menos nulos a remover.
  Consumidor que indexa chave opcional diretamente (`item["due_at"]`) deve
  passar a tratar ausência como falsy; é o único ajuste que esta mudança exige.

### Fixed
- **`import_graph` não perde mais dados em lote heterogêneo.** Quando a primeira
  linha do lote não trazia uma coluna que as demais traziam, a coluna desaparecia
  do INSERT inteiro e os valores das outras linhas eram descartados em silêncio —
  o import devolvia sucesso e o dado simplesmente não estava lá. Agora as colunas
  vêm da **união das chaves de todas as linhas**, na ordem da tabela; ausência numa
  linha vira `NULL` só naquela linha. Cobre `work_items`, `notes` e `dependencies`.

## [2.1.0] - 2026-10-19

Economicidade de contexto (RFC-003). Tudo é **aditivo e opt-in**: sem os novos
parâmetros, as respostas são byte-idênticas às de 2.0.1 — garantido por
caracterização versionada do payload, não por inspeção.

### Added
- **`get_context(verbosity)`** (FEAT-1): `compact` devolve counts, `next_item`
  reduzido e as listas como `[id,title,status,priority,stale_days]`, com
  `stale_total`/`stale_limit` explícitos; `standard` acrescenta `description`
  truncada em 200 chars. Medido numa placa de 42 itens: 34.896 → 1.340 chars.
- **`query_items(fields, compact)` e `get_blocked_items(fields, compact)`**
  (FEAT-2): projeção de colunas e página explícita (`has_more`/`next_offset`).
  Listagem de 50 itens: 39.640 → 6.804 chars (−82,8%), ≤150 chars por item.
  `fields` inexistente devolve erro estruturado com `field`, nunca silêncio.
- **Tabela `workspaces`** (FEAT-6b): a configuração saiu de `workspaces.json`
  para o mesmo SQLite dos work items, com `created_by`/`updated_by`; entra no
  `export_graph` e volta no `import_graph`. O `workspaces.json` legado é
  importado **uma vez**, quando a tabela está vazia.
- **Caracterização do contrato de leitura**: baseline versionado com `sha256`
  do payload normalizado de 11 pontos de leitura, com guarda contra regravação
  em CI.
- **`SCHEMA_VERSION` + `PRAGMA user_version`**: o schema passa a ter versão
  registrada, base para migração ordenada.

### Changed
- **`get_context` deixou de pagar N+1**: blockers são resolvidos em lote
  (125 → 12 consultas no full, 123 → 10 no compact, 115 → 2 de dependências),
  com payload idêntico. Guarda de orçamento de consultas na suíte.

### Fixed
- **Staleness em dias inteiros**: a regra era `(now - updated).days > 7`, que só
  vale a partir de 8 dias completos; a tradução para SQL marcava "7 dias e 1
  segundo" como stale. Corrigido para corte em 8/4 dias com `<=`.
- **`import_graph(mode="replace")` não apaga mais workspaces** quando o payload
  importado é anterior a esta versão e não traz a chave — antes, restaurar um
  backup antigo zerava a configuração em silêncio.
- **Migração falha alto**: `_run_migrations` engolia qualquer `OperationalError`;
  agora só tolera `duplicate column name`. Banco travado por outro agente no
  boot não deixa mais o schema incompleto em silêncio.
- **`__version__`** deixou de ser um literal parado em 0.8.0; passa a ler a
  versão instalada, e o `export_graph` reporta a versão real.

### Upgrade notes
- **Clientes MCP com `tools/list` em cache precisam reconectar**: `query_items`
  e `get_blocked_items` ganharam parâmetros e o `docs/TOOLS.md` mudou.
- `workspaces.json`, se existir ao lado do banco, é importado na primeira
  abertura e pode ser removido depois — não há nova leitura dele.
- Os novos modos são opt-in. Nada muda para quem não os pedir, inclusive o
  startup-hook que hoje chama `get_context()` sem argumentos.

## [2.0.1] - 2026-10-19

### Added
- **Payload bench** (`scripts/measure_payload.py` + `tests/test_measure_payload.py`): a deterministic
  64-item plate (8 arcs, 12 in `work`, stale items, a blocked dependency, one 5.000-char
  description) that measures `TextContent` + `structuredContent` bytes per call. The RFC-003
  acceptance criteria are numbers; this is the ruler that makes them verifiable.
- **RFC-003 — economia de contexto** (`docs/rfc/RFC-003-economia-de-contexto.md`): seis feats para
  cortar o custo de leitura do Orc, com baseline medido contra o board real. Inclui o achado do
  payload duplicado: as 31 tools anotadas `-> str` fazem o FastMCP emitir `TextContent` **e**
  `structuredContent`, dobrando toda resposta (−51% medido com `structured_output=False`).

### Fixed
- **Every tool response was sent twice** (FEAT-0, RFC-003): the 31 tools are annotated `-> str`
  and FastMCP wraps a scalar return into `structuredContent={"result": <the same string>}` on top
  of the `TextContent`. All 31 now declare `structured_output=False`, halving every response with
  no change to the payload, the return annotations or the tool schemas. Proven at three levels:
  in-process shape (`tests/test_structured_output.py`), real wire over stdio
  (`tests/test_wire_payload_e2e.py`) and byte measurement — all three fail on the pre-fix code.
  Client compatibility verified against **Kiro CLI 2.32.0** on a live stdio server: it lists the
  31 tools without `outputSchema` and executes them normally, so nothing depends on
  `structuredContent`.

### Upgrade note
- **Sessions already running must reconnect.** A client that cached `tools/list` from 2.0.0 still
  believes the 31 tools declare an `outputSchema`, so it rejects the new responses with
  `has an output schema but did not return structured content`. Nothing is wrong server-side: a
  fresh MCP session lists the tools without `outputSchema` and works. Restart or reconnect any
  long-lived client after upgrading — verified on 19/out with the live production server.

### Changed
- **Documentação reconciliada com o rename 2.0.0**: links do `CHANGELOG` apontam para
  `filhocf/orc-hestrator`; `AGENTS.md` corrige o nome da distribuição (`orc-hestrator-server`);
  `docs/BRING-YOUR-AGENT.md` corrige a versão de `/health` (1.5.0 → 2.0.0) e o nome da F7;
  `AGENTS.md` ganha uma seção "Current state" (versão, contagem de tools, fatias abertas).
- **Nota operacional:** o produto `task-orchestrator-py` foi aposentado em todas as máquinas em
  19/out/2026 (serviço, cron de sync, backups e env removidos). O checkout local passou a ser
  `~/git/orc`.

## [2.0.0] - 2026-10-18

### Changed (breaking)

- **Distribution renamed to `orc-hestrator-server`.** The name `orc-hestrator` is impossible on
  PyPI: its ultra-normalized form (`0rchestrat0r`) collides with the existing `orchestrator`
  project. The GitHub repository and the brand remain `orc-hestrator`.
- **MCP server identity:** `initialize` now reports `serverInfo.name = "orc"`; the version comes
  from `importlib.metadata` for the new distribution.
- **Environment variable precedence:** `ORC_DB`, `ORC_CONFIG` and `ORC_LANG` are the primary
  variables. `TASK_ORCHESTRATOR_DB` / `TASK_ORCHESTRATOR_CONFIG` still work as a fallback with a
  single deprecation warning; when both are set, the `ORC_*` variable wins.
- **Default database path** is now `~/.orc/tasks.db`. Continuity guard: if the old
  `~/.task-orchestrator/tasks.db` exists and the new path does not, the old file is used (with a
  one-time warning) instead of starting an empty database.
- **New console scripts:** `orc` (stdio MCP server), `orc-mcp` (explicit stdio alias), `orc-serve`
  (streamable-http server on `MCP_HOST`/`MCP_PORT`), `orc-ui` (lightweight board) and
  `orc-hestrator` (distribution-homonym script, so `uvx orc-hestrator-server` works). The legacy
  `task-orchestrator-py` / `task-orchestrator-ui` scripts remain as aliases that print a
  deprecation warning on stderr.
- **Transport is chosen by the entry point** (ADR-007), not by an environment variable: `orc`
  opens stdio, `orc-serve` opens `streamable-http`. `MCP_TRANSPORT` remains as an override for
  tests and edge cases.
- **`mcp` dependency capped at `<2`.** A clean install without this cap resolved `mcp 2.x`, where
  `mcp.server.fastmcp` no longer exists (FastMCP was renamed to MCPServer) and every entry point
  died at import. The cap now ships in the wheel metadata, not only in `uv.lock`.
- **`orc-serve` requires the `ui` extra.** The streamable-http transport needs `fastapi` +
  `uvicorn`, which live in the optional `ui` extra — not core. A core-only install now exits with
  code 2 and a clear pointer to `uvx --from 'orc-hestrator-server[ui]' orc-serve` (or
  `uv tool install 'orc-hestrator-server[ui]'`) instead of a raw import traceback.

## [1.5.1] - 2026-10-18

> 1.5.1 is the last release published under the old name (`task-orchestrator-py`). It carries the
> same code as 2.0.0 without the rename — only the metadata (version and a description pointing to
> `orc-hestrator-server`) differs.

### Fixed
- **UI assets/routes under a base path.** Absolute references (`src="/mascote.png"`, router
  `basename`) ignored Vite's `base`, resolving to the domain root and 404-ing when the SPA is
  served under a subpath (e.g. `/orc/ui/`). Now use `import.meta.env.BASE_URL` for the mascot
  logo (`Layout`, `Login`, `Overview`) and the `BrowserRouter` basename, and the favicon points
  to `mascote.png` (the removed `.svg` left the icon broken).

### Deployment notes
- The web extra (`fastapi`) is **optional** (`[project.optional-dependencies] ui`). Deploys must
  run `uv sync --extra ui`; a plain `uv sync` omits `fastapi` and the service restart-loops with
  `ModuleNotFoundError: fastapi`.
- Serving the SPA under a subpath: build with `vite build --base=/orc/ui/ (VITE_API_BASE=/orc/api)`
  and reverse-proxy `/orc/api/` to the backend. The initial admin is seeded from
  `ORC_ADMIN_USER`/`ORC_ADMIN_PASSWORD` on first boot when no user exists.
- First production deploy of the management UI + real auth validated live at
  `https://cfnarede.dev/orc/ui/` (login, session cookie, RBAC, real dashboard data).

## [1.5.0] - 2026-10-16

### Added
- **Decoupled React management UI** (`frontend/`, Vite + React 18 + TypeScript + Tailwind):
  9 screens consuming the REST API — login, dashboard/overview, live team presence
  (host/agent/session triple), kanban board, arcs tree, DAG graph (Cytoscape), task detail,
  admin/RBAC, profile. Design from Stitch (`docs/design/stitch/`). Dark/light theme.
  E2E navigation tests via playwright-with-yaml (`frontend/e2e/`).
- **REST API over the engine** (`web/api.py`, mounted at `/api` on the streamable-http app):
  reads (items, items/{id}, arcs, context, sessions, claims, metrics, graph, workspaces) and
  writes (advance, claims). Thin layer reusing the engine — see `docs/specs/SPEC-http-api.md`.
- **User authentication + RBAC** (`engine/users.py`, `docs/specs/SPEC-user-auth-rbac.md`):
  `POST /api/auth/login|logout`, `GET /api/auth/me`; scrypt password hashing (stdlib, per-user
  salt, constant-time compare); opaque session token in an HTTP-only cookie with server-side
  revocation; roles `admin`/`user`; `require_admin` guard; `GET/POST /api/users` (admin-only,
  never leaks the hash); initial admin seeded from `ORC_ADMIN_USER`/`ORC_ADMIN_PASSWORD`.
  `get_current_user` now validates the session cookie (the SPEC-http-api R10 extension point),
  without changing existing route signatures. Login is constant-time (no user enumeration) and
  the cookie honors `X-Forwarded-Proto`/`ORC_COOKIE_SECURE` behind a TLS proxy.

### Security
- All `/api/*` routes except `/api/auth/login`, `/api/auth/logout` and `/health` require a
  valid user session (401 otherwise).

## [1.4.0] - 2026-10-16

### Added
- **Central session registry / presence** incorporated into the Orc: triple identity
  (hostname, agent_id, session_id), heartbeat-based liveness, and claims — resolving
  cross-session conflicts by session_id.

## [1.3.0] - 2026-10-15

### Added
- **OAuth2 resource-server authentication** (opt-in, `MCP_OAUTH_ENABLED`, default off):
  opaque pre-shared tokens verified via FastMCP's native `TokenVerifier`. Second barrier
  behind the nginx edge basic auth (ADR-004). `/health` stays public. Pluggable verifier so a
  future JWT/IdP (corporate SSO) can replace it without touching the rest of the service.
- **Per-request agent attribution (`agent_id`)** (ADR-005): writes record who performed them
  via `created_by`/`updated_by` on `work_items`, `created_by` on `notes` and `dependencies`.
  Resolution precedence: explicit arg → `X-Agent-ID` header → `MCP_AGENT_ID` env → OAuth
  client_id → null. Resolved per request via a contextvar with mandatory reset (no leakage
  between requests). Additive, nullable migration — anonymous writes still succeed.
- `get_project_graph_metrics` tool — critical path, impact scores, and bottleneck detection
  over the dependency graph (previously planned).

### Changed
- **Internal refactor:** the monolithic `engine.py` (~1960 LOC) was split into an `engine/`
  package of 11 cohesive modules (`base`, `items`, `transitions`, `dependencies`, `notes`,
  `queries`, `trees`, `metrics`, `archive`, `portability`, `workspace_view`) behind a
  re-export facade. **No public API change** — all tools, signatures, and the `engine.X`
  import surface are preserved. Improves maintainability and navigation.
- CI hardening: ruff config pinned (`[tool.ruff]`), actions SHA-pinned, per-job timeouts,
  docs-only `paths-ignore`, and a markdown link-check workflow.

### Fixed
- `import_graph` now orders items topologically (parent-before-child at any depth), fixing a
  `FOREIGN KEY constraint failed` crash on hierarchies ≥3 levels deep. Orphan parents are
  normalized to roots instead of crashing. Removes the FK-off workaround used during the
  cutover.
- `AGENTS.md` architecture section now reflects the real module layout (it described modules
  that never existed).

## [1.2.1] - 2026-06-23

### Added
- `parent_id` is now updatable via `manage_items(update)` — enables reparenting items between ARCs
- Validation: parent exists, no self-parent, max depth 4. Set to `""` to unparent.

## [1.2.0] - 2026-06-23

### Added
- `/health` endpoint via `@mcp.custom_route` (GET, returns status/version/uptime)

## [1.1.0] - 2026-06-08

### Added
- `get_execution_stack` tool — context stack for session resume after interruptions
- `manage_archive` tool — auto-archive done items older than N days
- `manage_checkpoints` tool — create/list/restore/verify JSON snapshots
- `get_workspace_context` tool — workspace payload at 3 verbosity levels (minimal/standard/full)
- Workspace `repos` and `conventions` fields

### Changed
- Test suite expanded to 114+ tests

## [1.0.0] - 2026-05-28

### Added
- **StreamableHTTP transport** on port 3201 (`MCP_TRANSPORT=streamable-http`)
- systemd service support (task-orchestrator.service)
- `manage_workspaces` tool — create/update/delete/list workspace configs
- Workspace-scoped queries in `get_context`, `get_next_item`, `get_metrics`
- `export_graph` and `import_graph` tools with workspace/tag filtering
- Kanban Web UI skeleton (FastAPI + HTMX + Tailwind)

### Changed
- Default transport remains stdio for backward compatibility

## [0.9.0] - 2026-05-18

### Added
- Workspace entity — tag mapping, memory_tags, description
- Workspace-filtered `get_context`, `get_next_item`, `get_metrics`
- Memory tag bridge (2 levels: inline + reference via memory service)
- Auto-checkpoint JSON resilience (corruption recovery)

## [0.8.0] - 2026-05-10

### Added
- Scheduling support (cron expressions, `next_run_at`)
- `due_at` field on work items with deadline alerts

### Fixed
- croniter naive/aware datetime handling
- CI pipeline stabilization

## [0.7.0] - 2026-05-06

### Added
- `get_metrics` tool — throughput per week, lead time, WIP, stale ratio
- Priority and tag breakdowns in metrics
- Configurable lookback period (days param)
- `complete_tree` tool — batch-complete descendants in topological order
- `create_work_tree` — atomically create root + children + dependencies

## [0.6.1] - 2026-05-02

### Added
- Comprehensive test suite with 35+ tests (#9)

### Changed
- Comprehensive README rewrite (#11)

## [0.6.0] - 2026-05-02

### Added
- Stale item detection in get_context (#4)
- Structured ToolError responses (#3)
- Filter query_items by tags (#2)
- Short hex ID resolution (4+ chars) (#1)

## [0.5.0] - 2026-04-10

### Added
- Full feature parity with original Kotlin task-orchestrator

## [0.4.0] - 2026-04-10

### Added
- Auto-reopen parent items from terminal status
- `unblock_at` threshold for dependencies
- README documentation

## [0.3.0] - 2026-04-10

### Added
- MCP prompts (workflow skills)
- Note schema gates

## [0.2.0] - 2026-04-10

### Added
- Full feature parity with original task-orchestrator
- Note schemas with gate enforcement
- Lifecycle modes
- GitHub Actions workflow for PyPI trusted publishing
- Initial Python port of task-orchestrator

[Unreleased]: https://github.com/filhocf/orc-hestrator/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/filhocf/orc-hestrator/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/filhocf/orc-hestrator/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/filhocf/orc-hestrator/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/filhocf/orc-hestrator/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/filhocf/orc-hestrator/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/filhocf/orc-hestrator/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/filhocf/orc-hestrator/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/filhocf/orc-hestrator/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/filhocf/orc-hestrator/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/filhocf/orc-hestrator/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/filhocf/orc-hestrator/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/filhocf/orc-hestrator/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/filhocf/orc-hestrator/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/filhocf/orc-hestrator/releases/tag/v0.2.0
