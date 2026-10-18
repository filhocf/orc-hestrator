"""MCP Onboarding — o servidor que se explica (fatia F1, i18n G4.1).

Implementa a fatia F1 da SPEC-bring-your-agent-onboarding:

- tool `orc_onboarding(client_type, lang)`: texto com as seis seções
  invariante de idioma (`model`, `session_cycle`, `verbs`, `gates`,
  `antipatterns`, `examples`), os quatro status, os seis triggers e as
  regras do R3. Variantes hermes/kiro/cli, com `generic` para client_type
  desconhecido. Inglês canônico + pt-BR como segundo idioma (R9/R10).
- resources por idioma (R12): os URIs base `orc://onboarding`,
  `orc://workflow` e `orc://glossary` servem o idioma resolvido pela
  precedência do R9 (padrão `en`); cada um tem o par `/pt-br` com o idioma
  fixo (seis URIs).

Resolução de idioma (R9): argumento `lang` → env `ORC_LANG` → header
`Accept-Language` (somente transporte HTTP, via request context do FastMCP)
→ `en`. Idioma não suportado cai em `en` sem erro.

Somente leitura: nenhuma das rotas aqui toca o banco (R8). Teto rígido de
6.000 caracteres por variante × idioma (R11) — custo de contexto é requisito.
"""

import os

from mcp.server.fastmcp import FastMCP

# Teto rígido de contexto por variante × idioma (R4/R11).
_MAX_CHARS = 6000

# Variantes conhecidas de client_type (R2); qualquer outra cai em `generic`.
KNOWN_CLIENT_TYPES = ("hermes", "kiro", "cli")
_GENERIC = "generic"

# Idioma canônico (R9): `en`; segundo idioma: `pt-BR`.
_DEFAULT_LANG = "en"

# ---------------------------------------------------------------------------
# Prosa em EN (idioma canônico). A estrutura — marcadores de seção, `variant:`
# e `lang:` — é invariante de idioma (R10); só a prosa é localizada.
# ---------------------------------------------------------------------------

_EN_BASE = """model
WorkItems form a graph: parent/children hierarchy (up to 4 levels) and
directed dependencies. Each item has title, status, priority
(critical/high/medium/low), complexity (1-10), tags, notes and due_at.
Item status: queue -> work -> review -> done (auxiliary: blocked,
cancelled).

session_cycle
Register your session before working: agent_register returns session_id —
reuse it. Keep agent_heartbeat(session_id) every 2-3 min. End with
agent_end(session_id) on exit (releases your claims in CASCADE).

verbs
Items: manage_items (create/update/delete), query_items (list/get/children/
overview). Progression: advance_item(item_id, trigger). Triggers: start,
complete, block, resume, cancel, reopen. Notes: manage_notes. Dependencies:
manage_dependencies. Atomic tree: create_work_tree. Claims: claim
(subject_type, subject_ref, session_id); release(subject_type, subject_ref,
session_id); conflicts(subjects_json, session_id).

gates
Every transition is validated against satisfied dependencies and schema
notes. A transition only unlocks when all prerequisites are ok. Use
get_next_status(item_id, trigger) to preview the outcome without side
effects.

antipatterns
- Working without a registered session (no session_id).
- Grabbing an item without a claim: call claim(subject_type, subject_ref,
  session_id) before taking an item.
- Creating an item without searching first: search before creating by
  similar title (duplicates poison the graph).
- Using the board as a conversation diary.

examples
- Start: get_context() for the state; get_next_item() for the next action.
- Typical session: agent_register() -> claim(subject_type="work_item",
  subject_ref=<item_id>, session_id) -> advance_item(<item_id>, "start") ...
  advance_item(<item_id>, "complete") -> agent_end(session_id)."""

_EN_VARIANTS: dict[str, str] = {
    "hermes": (
        "connection (hermes)\n"
        "Identity: identity_header (name: X-Agent-ID, value_from: profile)\n"
        "— your agent_id becomes the Hermes profile name. Auth by header:\n"
        "Bearer with the server's OAuth2 enabled, Basic at the reverse-proxy\n"
        "edge. Tool cut is client-side config (the server does not filter\n"
        "tools): nucleo (main agent), leitura (subagents), completo\n"
        "(operations). Full guide: docs/BRING-YOUR-AGENT.md."
    ),
    "kiro": (
        "connection (kiro)\n"
        "Connect through the MCP URL (https://host/orc/mcp) with auth\n"
        "headers. Identity via X-Agent-ID header or MCP_AGENT_ID env."
    ),
    "cli": (
        "connection (cli)\n"
        "Run `uv run orc` (stdio) or `orc-serve` for\n"
        "streamable-http (port via MCP_PORT, host via MCP_HOST). Set\n"
        "MCP_AGENT_ID for the presence identity.\n"
        "Note: streamable-http needs the `ui` extra (`uv sync --extra ui`);\n"
        "without fastapi the process dies with ModuleNotFoundError."
    ),
    _GENERIC: (
        "connection (generic)\n"
        "Connect to the MCP server (stdio or streamable-http). Register\n"
        "your session with agent_register; identity comes from X-Agent-ID\n"
        "or MCP_AGENT_ID."
    ),
}

_EN_WORKFLOW = """Orc — workflow

Item lifecycle: queue -> work -> review -> done.
Auxiliary states: blocked (paused) and cancelled (closed).

Triggers (advance_item) and their effects:
- start: advance to the next phase (queue->work, work->review, review->done).
- complete: jump straight to done.
- block: pause the item (-> blocked).
- resume: resume a blocked item.
- cancel: close without completion (-> cancelled).
- reopen: reopen a done/cancelled item back to queue.

Session cycle: register your session before working (agent_register returns
session_id), keep agent_heartbeat, and claim before taking an item. On
finish, agent_end releases the claims.

Gates: every transition is validated against satisfied dependencies and
schema notes. Use get_next_status to preview the transition without side
effects.
"""

_EN_GLOSSARY = """Orc — glossary

- WorkItem: unit of work; has title, status, priority, complexity,
  tags, notes and due_at; supports hierarchy (parent/children) and
  dependencies.
- Status: queue (waiting), work (in progress), review (under review), done
  (finished), blocked (paused), cancelled (closed).
- Trigger: action that moves the item — start, complete, block, resume,
  cancel, reopen.
- Dependency: directed edge; the target only advances when the blocker
  reaches unblock_at.
- Session: presence record (agent_register -> session_id) identified by the
  triple hostname/agent_id/session_id. Register your session before working.
- Claim: reservation of an item or resource by a session —
  claim(subject_type, subject_ref, session_id). Claim before taking an item
  to avoid two agents on the same work.
- Gate: prerequisite check (dependencies + schema notes) before a transition.
- Workspace: tag group scoping queries.
- Anti-duplication rule: search for a similar title before creating an item.
"""

# ---------------------------------------------------------------------------
# Prosa em PT-BR (segundo idioma). Mesmos marcadores invariantes (R10).
# ---------------------------------------------------------------------------

_PT_BASE = """model
WorkItems formam um grafo: hierarquia parent/children (até 4 níveis) e
dependências direcionadas. Cada item tem title, status, priority
(critical/high/medium/low), complexity (1-10), tags, notes e due_at.
Status do item: queue -> work -> review -> done (auxiliares: blocked,
cancelled).

session_cycle
Registre a sessão antes de trabalhar: agent_register devolve session_id —
reutilize-o. Mantenha agent_heartbeat(session_id) a cada 2-3 min. Encerre
com agent_end(session_id) ao sair (libera seus claims em CASCADE).

verbs
Itens: manage_items (create/update/delete), query_items (list/get/children/
overview). Progressão: advance_item(item_id, trigger). Triggers: start,
complete, block, resume, cancel, reopen. Notas: manage_notes. Dependências:
manage_dependencies. Árvore atômica: create_work_tree. Claims: claim
(subject_type, subject_ref, session_id); release(subject_type, subject_ref,
session_id); conflicts(subjects_json, session_id).

gates
Cada transição é validada contra dependências satisfeitas e notes de
schema. A transição só libera com todos os pré-requisitos ok. Use
get_next_status(item_id, trigger) para prever o resultado sem efeito
colateral.

antipatterns
- Trabalhar sem sessão registrada (sem session_id).
- Pegar item sem claim: chame claim(subject_type, subject_ref,
  session_id) antes de pegar um item.
- Criar item sem buscar antes por título semelhante — buscar antes de criar
  (duplicatas envenenam o grafo).
- Usar o board como diário de conversa.

examples
- Começar: get_context() para o estado; get_next_item() para a próxima
  ação.
- Sessão típica: agent_register() -> claim(subject_type="work_item",
  subject_ref=<item_id>, session_id) -> advance_item(<item_id>, "start") ...
  advance_item(<item_id>, "complete") -> agent_end(session_id)."""

_PT_VARIANTS: dict[str, str] = {
    "hermes": (
        "conexão (hermes)\n"
        "Identidade: identity_header (name: X-Agent-ID, value_from: profile)\n"
        "— o agent_id vira o nome do perfil Hermes. Autenticação por header:\n"
        "Bearer com o OAuth2 do servidor ligado, Basic na borda do proxy\n"
        "reverso. O recorte de tools é configuração do cliente (o servidor\n"
        "não filtra tools): nucleo (agente principal), leitura (subagentes),\n"
        "completo (operação). Guia completo: docs/BRING-YOUR-AGENT.md."
    ),
    "kiro": (
        "conexão (kiro)\n"
        "Entre pelo MCP via URL (https://host/orc/mcp) com headers de\n"
        "autenticação. A identidade pode vir por header X-Agent-ID ou env\n"
        "MCP_AGENT_ID."
    ),
    "cli": (
        "conexão (cli)\n"
        "Rode `uv run orc` (stdio) ou `orc-serve` para\n"
        "streamable-http (porta via MCP_PORT, host via MCP_HOST). Defina\n"
        "MCP_AGENT_ID para a identidade na presença. Atenção: streamable-http\n"
        "exige o extra `ui` (`uv sync --extra ui`); sem fastapi o processo\n"
        "morre com ModuleNotFoundError."
    ),
    _GENERIC: (
        "conexão (genérica)\n"
        "Conecte-se ao servidor MCP (stdio ou streamable-http). Registre a\n"
        "sessão com agent_register; a identidade vem de X-Agent-ID ou\n"
        "MCP_AGENT_ID."
    ),
}

_PT_WORKFLOW = """Orc — fluxo de trabalho

Ciclo de vida do item: queue -> work -> review -> done.
Estados auxiliares: blocked (pausado) e cancelled (encerrado).

Triggers (advance_item) e seus efeitos:
- start: avança para a próxima fase (queue->work, work->review, review->done).
- complete: pula direto para done.
- block: pausa o item (-> blocked).
- resume: retoma um item bloqueado.
- cancel: encerra sem conclusão (-> cancelled).
- reopen: reabre um item done/cancelled de volta para queue.

Ciclo de sessão: registre a sessão antes de trabalhar (agent_register devolve
session_id), mantenha agent_heartbeat e faça claim antes de pegar um item.
Ao terminar, agent_end libera os claims.

Gates: cada transição é validada contra dependências satisfeitas e notes de
schema. Use get_next_status para prever a transição sem efeito colateral.
"""

_PT_GLOSSARY = """Orc — glossário

- WorkItem: unidade de trabalho; tem title, status, priority, complexity,
  tags, notes e due_at; suporta hierarquia (parent/children) e dependências.
- Status: queue (fila), work (em andamento), review (revisão), done
  (concluído), blocked (pausado), cancelled (cancelado).
- Trigger: ação que move o item — start, complete, block, resume, cancel,
  reopen.
- Dependência: aresta direcionada; o destino só avança quando o bloqueante
  atinge unblock_at.
- Sessão: registro de presença (agent_register -> session_id), tripla
  hostname/agent_id/session_id. Registre a sessão antes de trabalhar.
- Claim: reserva de um item ou recurso por uma sessão —
  claim(subject_type, subject_ref, session_id). Faça claim antes de pegar um
  item para evitar dois agentes no mesmo trabalho.
- Gate: verificação de pré-requisitos (dependências + notes de schema) antes
  de uma transição.
- Workspace: grupo de tags para escopar consultas.
- Regra anti-duplicata: busque antes de criar item por título semelhante.
"""


# ---------------------------------------------------------------------------
# Resolução de variante e de idioma (R2/R9)
# ---------------------------------------------------------------------------


def _normalize_variant(client_type: str) -> str:
    """Mapeia client_type para a variante servida (desconhecido -> generic)."""
    variant = (client_type or "").strip().lower()
    return variant if variant in KNOWN_CLIENT_TYPES else _GENERIC


def _normalize_lang(code: str) -> str:
    """Mapeia um tag de idioma para o código canônico suportado, ou '' se não."""
    tag = (code or "").strip().lower().replace("_", "-")
    if not tag:
        return ""
    if tag == "en" or tag.startswith("en-"):
        return "en"
    if tag in ("pt", "pt-br"):
        return "pt-BR"
    return ""


def _parse_accept_language(header: str) -> str:
    """Primeiro tag de idioma de um header Accept-Language (ignora q-values)."""
    for part in header.split(","):
        tag = part.split(";")[0].strip()
        if tag and tag != "*":
            return tag
    return ""


def _accept_language(mcp: FastMCP | None) -> str:
    """Lê Accept-Language do request context do FastMCP (só transporte HTTP).

    Sem request context (stdio/in-process) devolve '' e o chamante degrada
    para o default (R9). Mesmo padrão de _resolve_agent_id em server.py.
    """
    if mcp is None:
        return ""
    try:
        ctx = mcp.get_context()
        request_context = getattr(ctx, "request_context", None)
        request = getattr(request_context, "request", None) if request_context else None
        headers = getattr(request, "headers", None) if request else None
        if headers is None:
            return ""
        value = headers.get("accept-language", "")
        return value.strip() if isinstance(value, str) else ""
    except Exception:
        return ""


def _resolve_lang(mcp: FastMCP | None, lang: str = "") -> str:
    """Resolve o idioma servido (R9): argumento → env ORC_LANG →
    Accept-Language (HTTP) → `en`.

    Idioma não suportado em qualquer nível cai em `en` sem erro (R9).
    """
    arg = (lang or "").strip()
    if arg:
        normalized = _normalize_lang(arg)
        return normalized if normalized else _DEFAULT_LANG
    env_value = os.environ.get("ORC_LANG", "").strip()
    if env_value:
        normalized = _normalize_lang(env_value)
        return normalized if normalized else _DEFAULT_LANG
    header = _accept_language(mcp)
    if header:
        normalized = _normalize_lang(_parse_accept_language(header))
        if normalized:
            return normalized
    return _DEFAULT_LANG


def _header(lang: str, variant: str) -> str:
    """Cabeçalho com os marcadores invariantes `variant:` e `lang:` (R10)."""
    title = (
        "Orc — persistent work-item orchestrator for AI agents."
        if lang == "en"
        else "Orc — orquestrador de trabalho persistente para agentes de IA."
    )
    return f"{title}\nvariant: {variant}\nlang: {lang}"


def build_onboarding_text(
    client_type: str = "hermes", lang: str = "", mcp: FastMCP | None = None
) -> str:
    """Monta o texto de onboarding para a variante e o idioma resolvidos.

    `client_type`: hermes/kiro/cli; desconhecido cai em `generic` sem erro
    (R2). `lang`: '' resolve pela precedência do R9 (env → Accept-Language
    quando disponível → `en`); valor não suportado cai em `en`. O marcador
    `lang:` declara o código canônico servido (R10). Enforce o teto rígido
    de 6.000 caracteres por variante × idioma (R11).
    """
    variant = _normalize_variant(client_type)
    resolved = _resolve_lang(mcp, lang)
    base = _EN_BASE if resolved == "en" else _PT_BASE
    variants = _EN_VARIANTS if resolved == "en" else _PT_VARIANTS
    text = f"{_header(resolved, variant)}\n\n{base}\n\n{variants[variant]}"
    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS].rstrip()
    return text


def build_workflow_text(mcp: FastMCP | None = None) -> str:
    """Prosa do workflow no idioma resolvido pela precedência do R9 (default `en`).

    Mesma resolução da tool e do resource `orc://onboarding`: sem argumento, o
    idioma vem de env `ORC_LANG` e, em transporte HTTP, do header
    `Accept-Language` (request context do FastMCP) antes do default `en` (R12).
    """
    return _PT_WORKFLOW if _resolve_lang(mcp, "") == "pt-BR" else _EN_WORKFLOW


def build_glossary_text(mcp: FastMCP | None = None) -> str:
    """Prosa do glossário no idioma resolvido pela precedência do R9 (default `en`).

    Mesma resolução da tool e do resource `orc://onboarding` (R12).
    """
    return _PT_GLOSSARY if _resolve_lang(mcp, "") == "pt-BR" else _EN_GLOSSARY


def register_onboarding(mcp: FastMCP) -> None:
    """Registra a tool `orc_onboarding` e os seis resources estáticos.

    Chamada no import de server.py para que a tool e os resources fiquem
    disponíveis assim que o módulo é carregado (como as demais tools).
    Os URIs de base servem o idioma resolvido pela precedência do R9
    (padrão `en`); os URIs `/pt-br` servem pt-BR fixo (R12).
    """

    @mcp.tool()
    def orc_onboarding(client_type: str = "hermes", lang: str = "") -> str:
        """Orc onboarding guide for this client type (read-only, no database).

        client_type: hermes, kiro or cli (unknown values fall back to the
        'generic' variant). lang: 'en' (canonical) or 'pt-BR'; empty resolves
        via env ORC_LANG, then the Accept-Language header (HTTP transport),
        then 'en'. Unknown languages fall back to 'en' without error.
        """
        return build_onboarding_text(client_type, lang, mcp)

    @mcp.resource(
        "orc://onboarding",
        name="onboarding",
        description=(
            "Orc onboarding — variant: hermes. Serves the language resolved "
            "per R9 (env ORC_LANG, then Accept-Language on HTTP; default en). "
            "Same text as the orc_onboarding tool."
        ),
    )
    def orc_onboarding_resource() -> str:
        return build_onboarding_text("hermes", "", mcp)

    @mcp.resource(
        "orc://onboarding/pt-br",
        name="onboarding pt-BR",
        description="Orc onboarding em pt-BR (variant: hermes).",
    )
    def orc_onboarding_pt_resource() -> str:
        return build_onboarding_text("hermes", "pt-BR")

    @mcp.resource(
        "orc://workflow",
        name="workflow",
        description=(
            "Orc workflow. Serves the language resolved per R9 "
            "(env ORC_LANG, then Accept-Language on HTTP; default en)."
        ),
    )
    def orc_workflow_resource() -> str:
        return build_workflow_text(mcp)

    @mcp.resource(
        "orc://workflow/pt-br",
        name="workflow pt-BR",
        description="Orc workflow em pt-BR: ciclo de vida, triggers, ciclo de sessão, gates.",
    )
    def orc_workflow_pt_resource() -> str:
        return _PT_WORKFLOW

    @mcp.resource(
        "orc://glossary",
        name="glossary",
        description=(
            "Orc glossary. Serves the language resolved per R9 "
            "(env ORC_LANG, then Accept-Language on HTTP; default en)."
        ),
    )
    def orc_glossary_resource() -> str:
        return build_glossary_text(mcp)

    @mcp.resource(
        "orc://glossary/pt-br",
        name="glossary pt-BR",
        description="Orc glossário em pt-BR: termos-chave em prosa.",
    )
    def orc_glossary_pt_resource() -> str:
        return _PT_GLOSSARY
