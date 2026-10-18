"""RED tests (G3) — fatia F1 "Bring Your Agent": servidor que se explica, i18n.

Espera de resultado: os testes NOVOS/ALTERADOS DEVEM FALHAR agora (a implementação
atual é PT-only e a tool não tem `lang`). Eles travam os AC1–AC7 e AC10–AC14 do spec
`docs/specs/SPEC-bring-your-agent-onboarding.md`, com inglês canônico e pt-BR como
segundo idioma:

- AC1  `test_tool_returns_sections` — as seis seções com os marcadores invariantes.
- AC2  `test_client_types` — hermes/kiro/cli/desconhecido sem exceção; variante
  declarada por `variant: <nome>` (desconhecido -> `generic`).
- AC3  `test_length_budget` — texto <= 6000 caracteres nas três variantes (mantido;
  o teto i18n 4×2 fica no AC12).
- AC4  `test_required_terms` — status/triggers (identificadores, sem tradução) +
  regras R3 em `en` (variante padrão, idioma canônico).
- AC5  `test_resources_registered` — os seis URIs listados e legíveis.
- AC6  `test_server_version` — `initialize` reporta a versão do pacote (prova por
  cliente MCP real em subprocesso — NÃO removível).
- AC7  `test_empty_db` — banco vazio (tmp_path): tool e os seis resources respondem.
- AC10 `test_i18n_sections` — as seis seções com os MESMOS marcadores invariantes em
  `en` e `pt-BR`.
- AC11 `test_lang_resolution` — precedência: argumento > env `ORC_LANG` > default;
  idioma desconhecido cai em `en`; o texto declara `lang: <código>`.
- AC12 `test_len_budget_all_langs` — variante × idioma (4 × 2) dentro de 6.000 chars.
- AC13 `test_resources_per_lang` — os seis URIs listados/legíveis com prosa no idioma
  certo (base -> `en`, `/pt-br` -> `pt-BR`).
- AC14 `test_prose_is_localized` — a prosa difere entre idiomas enquanto os marcadores
  invariantes são idênticos.
- AC15/AC16 `test_base_resources_honor_accept_language` — sob real HTTP
  (streamable-http em subprocesso + cliente MCP oficial com headers), os três URIs
  base (`orc://onboarding`, `orc://workflow`, `orc://glossary`) servem prosa pt-BR
  com `Accept-Language: pt-BR` (sem `lang` nem `ORC_LANG`) — R9/R12 no transporte
  HTTP (AC15) — e sem header (e sem `ORC_LANG`) servem prosa em inglês, o default
  `en` da precedência R9 (AC16).

Superfície REAL: `from task_orchestrator.server import mcp` + `mcp.call_tool` /
`mcp.list_resources` / `mcp.read_resource` (ferramentas e resources registrados no
import do módulo, como as outras tools). Banco: fixtures sintéticas em tmp_path (o
autouse `engine_db` do conftest já redireciona `db.DB_PATH` para um SQLite temporário
por teste); nenhum dado real do usuário é tocado.

Contrato fixado no G3 (a implementação GREEN deve obedecer sem margem de
interpretação):
- A tool aceita `lang` (`"en"` padrão, `"pt-BR"` segundo); precedência argumento >
  env `ORC_LANG` > default, idioma desconhecido cai em `en` sem erro (R9).
- Marcadores de seção `model`, `session_cycle`, `verbs`, `gates`, `antipatterns`,
  `examples` e `variant: <nome>` / `lang: <código>` são invariantes de idioma (em
  inglês nas duas línguas); variante desconhecida é servida como `generic` (R10).
- Prosa localizada (R3/G3): em `en`, `session` + `before working`, `claim`,
  `search before` + `title`; em `pt-BR`, `sessão` + `antes de trabalhar`, `claim`,
  `buscar antes` + `título`. Status e triggers são identificadores (não se traduzem)
  e são checados com fronteira de palavra, case-insensível.
"""

import asyncio
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

from task_orchestrator import db
from task_orchestrator.onboarding import build_onboarding_text
from task_orchestrator.server import mcp

# Marcadores de seção invariantes de idioma (R10) — iguais em `en` e `pt-BR`.
SECTIONS = ("model", "session_cycle", "verbs", "gates", "antipatterns", "examples")
# Status e triggers são identificadores: NÃO se traduzem (R3).
STATUSES = ("queue", "work", "review", "done")
TRIGGERS = ("start", "complete", "block", "resume", "cancel", "reopen")
# Variantes conhecidas de client_type (R2).
KNOWN_CLIENT_TYPES = ("hermes", "kiro", "cli")
# (client_type, variante servida) — desconhecido cai em `generic` (G3).
VARIANTS = (
    ("hermes", "hermes"),
    ("kiro", "kiro"),
    ("cli", "cli"),
    ("desconhecido", "generic"),
)
# Idiomas suportados (R9): canônico `en` + segundo `pt-BR`.
LANGS = ("en", "pt-BR")
# Resources: base (idioma resolvido pela precedência, padrão `en`) + sufixo `/pt-br` (R12).
RESOURCE_URIS = ("orc://onboarding", "orc://workflow", "orc://glossary")
ALL_RESOURCE_URIS = RESOURCE_URIS + tuple(u + "/pt-br" for u in RESOURCE_URIS)


# ---------------------------------------------------------------------------
# Helpers — superfície real (FastMCP) chamada de forma síncrona via asyncio.run
# ---------------------------------------------------------------------------


def _call_onboarding(client_type: str | None = None, lang: str | None = None) -> str:
    """Chamar a tool REAL `orc_onboarding` e devolver o texto servido.

    Normaliza os DOIS formatos de retorno do FastMCP in-process para o texto
    bruto, SEM travar o shape interno (parecer G5): `list[TextContent]` quando a
    tool não tem anotação de retorno, e `(content, structured)` (tuple) quando
    tem `-> str` — nesse caso usamos o primeiro elemento. Assim o GREEN pode
    restaurar `-> str` em `orc_onboarding` (consistente com as outras 30 tools)
    sem quebrar os testes. `client_type` e `lang` só entram nos arguments quando
    não são None (assim podemos omitir `lang` e exercitar a resolução por
    env/default no AC11).
    """
    arguments: dict[str, str] = {}
    if client_type is not None:
        arguments["client_type"] = client_type
    if lang is not None:
        arguments["lang"] = lang
    result = asyncio.run(mcp.call_tool("orc_onboarding", arguments))
    # FastMCP in-process: (content, structured) quando a tool tem `-> str`;
    # list[TextContent] quando não. Não travamos o shape — só o texto resultante.
    if isinstance(result, tuple):
        result = result[0]
    blocks = result if isinstance(result, list) else [result]
    texts = [b.text for b in blocks if getattr(b, "text", None)]
    text = "".join(texts)
    assert text.strip(), "orc_onboarding deve devolver texto não vazio"
    return text


def _resource_text(uri: str) -> str:
    """Ler um resource REAL via `mcp.read_resource` e devolver o conteúdo."""
    contents = list(asyncio.run(mcp.read_resource(uri)))
    assert contents, f"read_resource({uri}) não devolveu conteúdo"
    text = "".join(c.content for c in contents if isinstance(c.content, str))
    return text


def _words(text: str, *tokens: str) -> None:
    """Assertar tokens com fronteira de palavra (evita 'work' casar 'workflow').

    Identificadores (status/triggers) e marcadores invariantes são checados com
    fronteira de palavra, case-insensível (R3/G3).
    """
    low = text.lower()
    for token in tokens:
        assert re.search(rf"\b{re.escape(token)}\b", low), (
            f"termo obrigatório ausente do onboarding: {token!r}"
        )


def _declares_lang(text: str, code: str) -> bool:
    """True se o texto declara o marcador invariante `lang: <código>` (R10)."""
    return re.search(rf"lang:\s*{re.escape(code)}\b", text, re.IGNORECASE) is not None


def _declares_variant(text: str, variant: str) -> bool:
    """True se o texto declara o marcador invariante `variant: <nome>` (R10)."""
    return (
        re.search(rf"variant:\s*{re.escape(variant)}\b", text, re.IGNORECASE)
        is not None
    )


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ---------------------------------------------------------------------------
# AC1 — as seis seções (marcadores invariantes)
# ---------------------------------------------------------------------------


def test_tool_returns_sections():
    """AC1: cada variante de `orc_onboarding` devolve texto com as seis seções.

    Comportamento travado (R10): a tool existe (registrada no import), aceita
    client_type hermes/kiro/cli e o texto exibe as seis seções pelos marcadores
    invariantes `model`, `session_cycle`, `verbs`, `gates`, `antipatterns`,
    `examples` (em inglês nas duas línguas).
    """
    for client_type in KNOWN_CLIENT_TYPES:
        text = _call_onboarding(client_type)
        _words(text, *SECTIONS)


# ---------------------------------------------------------------------------
# AC2 — client_types conhecidos + desconhecido cai em `generic`
# ---------------------------------------------------------------------------


def test_client_types():
    """AC2: hermes/kiro/cli/desconhecido respondem sem exceção e declaram a variante.

    Comportamento travado (R2/G3): valor desconhecido não lança e o texto declara
    a variante servida pelo marcador invariante `variant: <nome>`; o desconhecido
    é servido como `generic`.
    """
    for client_type, variant in VARIANTS:
        text = _call_onboarding(client_type)
        assert _declares_variant(text, variant), (
            f"texto deve declarar 'variant: {variant}' para client_type={client_type!r}"
        )


# ---------------------------------------------------------------------------
# AC3 — teto de 6.000 caracteres (mantido)
# ---------------------------------------------------------------------------


def test_length_budget():
    """AC3: `len(texto) <= 6000` para as três variantes (R4 — custo de contexto).

    Mantido do contrato anterior; o teto estendido a variante × idioma (4 × 2)
    fica no AC12.
    """
    for client_type in KNOWN_CLIENT_TYPES:
        text = _call_onboarding(client_type)
        assert len(text) <= 6000, (
            f"variante {client_type!r} tem {len(text)} caracteres (teto: 6000)"
        )


# ---------------------------------------------------------------------------
# AC4 — termos obrigatórios (variante padrão, idioma canônico `en`)
# ---------------------------------------------------------------------------


def test_required_terms():
    """AC4: status, triggers e regras R3 em `en` (variante padrão, idioma canônico).

    Comportamento travado (R3/G3): os quatro status (queue/work/review/done) e os
    seis triggers (start/complete/block/resume/cancel/reopen) são identificadores e
    não se traduzem (fronteira de palavra, case-insensível); a prosa usa os tokens
    de `en`: `session` + `before working`, `claim`, `search before` + `title`.
    """
    text = _call_onboarding(client_type="hermes", lang="en")
    _words(text, *STATUSES)
    _words(text, *TRIGGERS)

    low = text.lower()
    assert "session" in low and "before working" in low, (
        "regra 'registre a sessão antes de trabalhar' (en) ausente"
    )
    assert "claim" in low, "regra 'faça claim antes de pegar um item' (en) ausente"
    assert "search before" in low and "title" in low, (
        "regra de buscar antes de criar item por título semelhante (en) ausente"
    )


# ---------------------------------------------------------------------------
# AC5 — resources MCP estáticos (os seis URIs)
# ---------------------------------------------------------------------------


def test_resources_registered():
    """AC5: os seis URIs estão listados e cada um lê conteúdo não vazio (R5/R12).

    Comportamento travado (R12): além do idioma canônico, o servidor expõe o par
    `orc://onboarding(/pt-br)`, `orc://workflow(/pt-br)` e `orc://glossary(/pt-br)`.
    """
    uris = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    for uri in ALL_RESOURCE_URIS:
        assert uri in uris, f"resource {uri} não registrado (list_resources)"
        assert _resource_text(uri).strip(), f"resource {uri} sem conteúdo legível"


# ---------------------------------------------------------------------------
# AC6 — serverInfo.version == versão do pacote, provado por cliente MCP real
# ---------------------------------------------------------------------------


def _run_client_initialize(port: int, deadline: float) -> str | None:
    """Conectar com o cliente oficial e devolver serverInfo.version (ou None).

    Tenta o handshake MCP completo (initialize) até `deadline` porque o
    subprocesso demora alguns segundos para ligar o uvicorn.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _attempt():
        # SIM117 desligado: ClientSession depende de (r, w) do context manager
        # externo, e os dois são async: não cabem num único `with`.
        async with streamablehttp_client(f"http://127.0.0.1:{port}/mcp") as (r, w, _):  # noqa: SIM117
            async with ClientSession(r, w) as session:
                init = await session.initialize()
                return init.serverInfo.version

    while time.monotonic() < deadline:
        try:
            return asyncio.run(_attempt())
        except Exception:
            time.sleep(0.5)
    return None


def test_server_version(tmp_path):
    """AC6: `initialize` reporta a versão do pacote, não a do SDK MCP (R6).

    Comportamento travado: sobe o servidor de verdade em subprocesso
    (MCP_TRANSPORT=streamable-http, porta livre, TASK_ORCHESTRATOR_DB em
    tmp_path) e um cliente MCP real compara `init.serverInfo.version` com
    `importlib.metadata.version(...)`. Orçamento total: ~60 s; teardown garantido
    no finally e nenhum `.db` fica no diretório do repositório (AC9).
    """
    from importlib.metadata import version as pkg_version

    repo = str(Path(__file__).resolve().parents[1])
    db_file = str(tmp_path / "ac6_live_server.db")

    port = _free_port()
    logs: list[str] = []

    def _reader(proc):
        assert proc.stdout is not None
        for line in proc.stdout:
            logs.append(line.decode(errors="replace"))
            if len(logs) > 500:  # teto p/ mensagem de falha legível
                del logs[:250]

    proc = subprocess.Popen(
        ["uv", "run", "orc-serve"],
        cwd=repo,
        env={
            **os.environ,
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": str(port),
            "TASK_ORCHESTRATOR_DB": db_file,
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    reader = threading.Thread(target=_reader, args=(proc,), daemon=True)
    reader.start()
    try:
        version = _run_client_initialize(port, time.monotonic() + 45)
        assert version is not None, (
            "servidor MCP não subiu em 45s; últimos logs:\n" + "".join(logs[-30:])
        )
        log_tail = "".join(logs[-30:])
        if "ModuleNotFoundError" in log_tail and "fastapi" in log_tail:
            raise AssertionError(
                "subprocesso morreu por ModuleNotFoundError: fastapi — "
                "rode `uv sync --extra ui` no repositório e tente de novo.\n" + log_tail
            )
        expected = pkg_version("orc-hestrator-server")
        assert version == expected, (
            f"serverInfo.version={version!r} != versão do pacote {expected!r} "
            "(R6: deve vir de importlib.metadata, não do SDK MCP)"
        )
    finally:
        import signal

        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.wait(timeout=10)
    # limpeza do artefato temporário do servidor
    try:
        Path(db_file).unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# AC7 — banco vazio
# ---------------------------------------------------------------------------


def test_empty_db(tmp_path, monkeypatch):
    """AC7: com banco vazio em tmp_path, tool e os seis resources respondem (R8).

    Comportamento travado: nenhuma das rotas de onboarding exige banco populado —
    com TASK_ORCHESTRATOR_DB apontando para um SQLite vazio em tmp_path,
    `orc_onboarding` devolve texto e os seis resources (AC5) leem conteúdo.
    """
    empty_db = tmp_path / "empty_tasks.db"
    monkeypatch.setenv("TASK_ORCHESTRATOR_DB", str(empty_db))
    db.DB_PATH = str(empty_db)
    db.init_db()  # schema vazio: nenhuma work item, nota ou sessão

    text = _call_onboarding()
    assert text.strip(), "tool deve responder com banco vazio"
    uris = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    for uri in ALL_RESOURCE_URIS:
        assert uri in uris, f"resource {uri} ausente com banco vazio"
        assert _resource_text(uri).strip(), (
            f"resource {uri} deve responder com banco vazio"
        )


# ---------------------------------------------------------------------------
# AC10 — as seis seções nos dois idiomas, com marcadores invariantes
# ---------------------------------------------------------------------------


def test_i18n_sections():
    """AC10: as seis seções aparecem nos MESMOS marcadores invariantes em en e pt-BR.

    Comportamento travado (R10): tanto em `lang="en"` quanto em `lang="pt-BR"`, o
    texto traz `model`, `session_cycle`, `verbs`, `gates`, `antipatterns`,
    `examples` (mesmos marcadores), além de declarar a variante (`variant: hermes`)
    e o idioma servido (`lang: <código>`).
    """
    for lang in LANGS:
        text = _call_onboarding(client_type="hermes", lang=lang)
        _words(text, *SECTIONS)
        assert _declares_variant(text, "hermes"), (
            f"'variant: hermes' ausente (lang={lang})"
        )
        assert _declares_lang(text, lang), f"'lang: {lang}' ausente do texto servido"


# ---------------------------------------------------------------------------
# AC11 — precedência de resolução de idioma
# ---------------------------------------------------------------------------


def test_lang_resolution(monkeypatch):
    """AC11: precedência completa e declaração do idioma servido (R9/G3).

    Comportamento travado, de forma isolada e determinística (env via monkeypatch):
    (1) argumento `lang` vence env `ORC_LANG`; (2) env `ORC_LANG` vence o default;
    (3) sem argumento e sem env -> default `en`; (4) idioma desconhecido cai em
    `en` sem erro. Em todos os casos o texto declara `lang: <código>` servido.
    """
    # (1) argumento explícito vence env ORC_LANG
    monkeypatch.setenv("ORC_LANG", "pt-BR")
    text = _call_onboarding(client_type="hermes", lang="en")
    assert _declares_lang(text, "en"), (
        "argumento lang='en' deve vencer env ORC_LANG=pt-BR"
    )
    assert "before working" in text.lower(), (
        "prosa em `en` esperada quando o argumento vence"
    )
    assert "antes de trabalhar" not in text.lower(), (
        "prosa pt-BR não deve vazar quando o argumento vence"
    )

    # (2) env ORC_LANG vence o default (sem argumento)
    text = _call_onboarding(client_type="hermes")
    assert _declares_lang(text, "pt-BR"), (
        "env ORC_LANG=pt-BR deve vencer o default (sem argumento)"
    )
    assert "antes de trabalhar" in text.lower(), (
        "prosa em `pt-BR` esperada quando o env vence"
    )

    # (3) sem argumento e sem env -> default `en`
    monkeypatch.delenv("ORC_LANG", raising=False)
    text = _call_onboarding(client_type="hermes")
    assert _declares_lang(text, "en"), "sem argumento/env o default deve ser `en`"

    # (4) idioma desconhecido cai em `en` sem erro
    text = _call_onboarding(client_type="hermes", lang="xx-XX")
    assert _declares_lang(text, "en"), "idioma desconhecido deve cair em `en`"
    assert not re.search(r"lang:\s*xx", text, re.IGNORECASE), (
        "idioma desconhecido não pode ser declarado no marcador lang:"
    )

    # (5) contexto in-process (sem HTTP): header ausente é ignorado sem erro e
    # a resolução cai em `en` (AC16) — exercita o caminho do request context
    # in-process da resolução R9 sem nenhuma requisição em jogo.
    text = build_onboarding_text("hermes", "", mcp)
    assert _declares_lang(text, "en"), (
        "in-process (sem HTTP), sem header, a resolução deve cair em `en` sem erro"
    )


# ---------------------------------------------------------------------------
# AC12 — teto de 6.000 caracteres para variante × idioma (4 × 2)
# ---------------------------------------------------------------------------


def test_len_budget_all_langs():
    """AC12: cada combinação variante × idioma (4 × 2) cabe em 6.000 caracteres (R11).

    Comportamento travado: as quatro variantes (hermes/kiro/cli/generic) cruzadas
    com os dois idiomas (en/pt-BR) — 8 combinações — servem o `lang:` e o `variant:`
    corretos (a grade é exercida de verdade) e cada uma respeita o teto de 6.000.
    """
    for client_type, variant in VARIANTS:
        for lang in LANGS:
            text = _call_onboarding(client_type=client_type, lang=lang)
            assert _declares_lang(text, lang), (
                f"combinação {client_type}/{lang} não serviu {lang!r}"
            )
            assert _declares_variant(text, variant), (
                f"combinação {client_type}/{lang} não declarou 'variant: {variant}'"
            )
            assert len(text) <= 6000, (
                f"combinação {client_type}/{lang} tem {len(text)} caracteres (teto: 6000)"
            )


# ---------------------------------------------------------------------------
# AC13 — resources por idioma: seis URIs com prosa no idioma certo
# ---------------------------------------------------------------------------


def test_resources_per_lang(monkeypatch):
    """AC13: os seis URIs são listados e legíveis, com prosa no idioma correto (R12).

    Comportamento travado: `orc://onboarding(/pt-br)`, `orc://workflow(/pt-br)` e
    `orc://glossary(/pt-br)` existem; os URIs de base servem o idioma canônico
    (prosa `en`: "before working") e os de sufixo `/pt-br` servem `pt-BR` (prosa
    "antes de trabalhar").
    """
    # Determinismo: os URIs de base devem servir o default (en) — env limpa.
    monkeypatch.delenv("ORC_LANG", raising=False)
    uris = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    en_uris = RESOURCE_URIS
    pt_uris = tuple(u + "/pt-br" for u in RESOURCE_URIS)

    for uri in (*en_uris, *pt_uris):
        assert uri in uris, f"resource {uri} não listado (list_resources)"
        assert _resource_text(uri).strip(), f"resource {uri} sem conteúdo legível"

    for uri in en_uris:
        assert "before working" in _resource_text(uri).lower(), (
            f"prosa `en` ausente no resource base {uri}"
        )
    for uri in pt_uris:
        assert "antes de trabalhar" in _resource_text(uri).lower(), (
            f"prosa `pt-BR` ausente no resource {uri}"
        )


# ---------------------------------------------------------------------------
# AC14 — prosa localizada, estrutura invariante
# ---------------------------------------------------------------------------


def test_prose_is_localized():
    """AC14: a prosa difere entre idiomas enquanto os marcadores invariantes são idênticos.

    Comportamento travado (R10/G3): para a mesma variante, `en` e `pt-BR` trazem os
    MESMOS marcadores (`model`, `session_cycle`, ..., `variant: hermes`) mas prosas
    diferentes — tokens de `en` (`before working`, `search before`) só em `en`, e
    tokens de `pt-BR` (`antes de trabalhar`, `buscar antes`) só em `pt-BR`.
    """
    text_en = _call_onboarding(client_type="hermes", lang="en").lower()
    text_pt = _call_onboarding(client_type="hermes", lang="pt-BR").lower()

    # estrutura invariante: mesmos marcadores nas duas línguas
    _words(text_en, *SECTIONS)
    _words(text_pt, *SECTIONS)
    assert _declares_variant(text_en, "hermes"), "'variant: hermes' ausente em `en`"
    assert _declares_variant(text_pt, "hermes"), "'variant: hermes' ausente em `pt-BR`"

    # prosa localizada: tokens de cada idioma só na sua língua
    for token in ("before working", "search before"):
        assert token in text_en, f"prosa `en` {token!r} ausente"
        assert token not in text_pt, f"prosa `en` {token!r} vazou para `pt-BR`"
    for token in ("antes de trabalhar", "buscar antes"):
        assert token in text_pt, f"prosa `pt-BR` {token!r} ausente"
        assert token not in text_en, f"prosa `pt-BR` {token!r} vazou para `en`"


# ---------------------------------------------------------------------------
# AC15/AC16 — nível HTTP real: Accept-Language nos resources de URI base (R9/R12)
# ---------------------------------------------------------------------------


def _http_read_resources(
    port: int,
    headers: dict[str, str] | None,
    uris: tuple[str, ...],
    deadline: float,
) -> dict[str, str] | None:
    """Conectar ao servidor real (streamable-http) e ler resources com os headers.

    Repete o handshake completo (initialize + reads) até `deadline` porque o
    subprocesso demora alguns segundos para ligar o uvicorn. Devolve
    `{uri: texto servido}` ou None se esgotar o prazo. `headers=None` liga
    sem header `Accept-Language` (o default `en` da precedência R9 deve
    valer por ausência, não por um valor explícito).
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _attempt() -> dict[str, str]:
        out: dict[str, str] = {}
        # SIM117 desligado: ClientSession depende de (r, w) do context manager
        # externo, e os dois são async: não cabem num único `with`.
        async with streamablehttp_client(  # noqa: SIM117
            f"http://127.0.0.1:{port}/mcp", headers=headers
        ) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                for uri in uris:
                    result = await session.read_resource(uri)
                    out[uri] = "".join(
                        c.text for c in result.contents if getattr(c, "text", None)
                    )
        return out

    while time.monotonic() < deadline:
        try:
            return asyncio.run(_attempt())
        except Exception:
            time.sleep(0.5)
    return None


def _http_call_onboarding(
    port: int, headers: dict[str, str] | None, deadline: float
) -> str | None:
    """Conectar ao servidor real (streamable-http) e chamar a tool REAL
    `orc_onboarding` SEM argumentos (a precedência R9 decide) com os headers.

    Devolve o texto servido ou None se esgotar o prazo. Hardening do AC15:
    a TOOL deve honrar o `Accept-Language`, não só os resources.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _attempt() -> str:
        # SIM117 desligado: ClientSession depende de (r, w) do context manager
        # externo, e os dois são async: não cabem num único `with`.
        async with streamablehttp_client(  # noqa: SIM117
            f"http://127.0.0.1:{port}/mcp", headers=headers
        ) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                result = await session.call_tool("orc_onboarding", {})
        return "".join(c.text for c in result.content if getattr(c, "text", None))

    while time.monotonic() < deadline:
        try:
            return asyncio.run(_attempt())
        except Exception:
            time.sleep(0.5)
    return None


def _start_http_server(
    repo: str,
    db_file: str,
    port: int,
    env_extra: dict[str, str] | None = None,
) -> tuple[subprocess.Popen, list[str]]:
    """Sobe o servidor de verdade em subprocesso (MCP_TRANSPORT=streamable-http).

    `ORC_LANG` é removido do ambiente herdado e `env_extra` aplicado depois —
    o env do servidor é explícito e determinístico (precedência R9). Devolve
    `(proc, logs)` com os logs capturados em thread.
    """
    logs: list[str] = []

    def _reader(proc):
        assert proc.stdout is not None
        for line in proc.stdout:
            logs.append(line.decode(errors="replace"))
            if len(logs) > 500:  # teto p/ mensagem de falha legível
                del logs[:250]

    env = {
        **os.environ,
        "MCP_TRANSPORT": "streamable-http",
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": str(port),
        "TASK_ORCHESTRATOR_DB": db_file,
    }
    env.pop("ORC_LANG", None)  # determinístico: só o env explícito vale
    if env_extra:
        env.update(env_extra)
    proc = subprocess.Popen(
        ["uv", "run", "orc-serve"],
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    reader = threading.Thread(target=_reader, args=(proc,), daemon=True)
    reader.start()
    return proc, logs


def _stop_http_server(proc: subprocess.Popen) -> None:
    """Mata o processo-grupo do servidor (teardown garantido)."""
    import signal

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()
    proc.wait(timeout=10)


def test_base_resources_honor_accept_language(tmp_path):
    """AC15/AC16: os URIs base e a tool resolvem o idioma pelo Accept-Language (R9/R12).

    Comportamento travado no transporte real (não in-process): o servidor sobe em
    subprocesso (MCP_TRANSPORT=streamable-http, porta livre, TASK_ORCHESTRATOR_DB
    em tmp_path) e o cliente MCP oficial passa headers. Sem `lang` (tool) nem
    `ORC_LANG` (env), o header é o único nível de precedência R9 em jogo:

    - AC15: com `Accept-Language: pt-BR`, `orc://onboarding`, `orc://workflow` e
      `orc://glossary` (URIs base, sem sufixo) servem prosa pt-BR
      ("antes de trabalhar") — e a TOOL `orc_onboarding` (sem `lang`) também
      honra o header: o texto servido declara `lang: pt-BR` (hardening).
    - AC16: sem header (e sem `ORC_LANG`), os mesmos URIs base servem prosa em
      inglês ("before working") — o default `en` da precedência R9.
      Hardening: com `ORC_LANG=en` no servidor, o env vence o header
      `Accept-Language: pt-BR` (segundo subprocesso, env explícito).

    Os URIs fixos `/pt-br` não estão em causa aqui (R12, coberto pelo AC13).
    Orçamento total: ~60 s; teardown garantido no finally e nenhum `.db` fica no
    diretório do repositório (AC9).
    """
    repo = str(Path(__file__).resolve().parents[1])
    db_file = str(tmp_path / "ac15_accept_language.db")
    db_file_env = str(tmp_path / "ac16_orc_lang_wins.db")

    port = _free_port()
    port_env = _free_port()

    # Servidor 1: sem ORC_LANG — o header é o único nível de precedência em jogo
    proc, logs = _start_http_server(repo, db_file, port)
    try:
        # AC15 — Accept-Language: pt-BR -> prosa pt-BR nos três URIs base
        served_pt = _http_read_resources(
            port,
            {"Accept-Language": "pt-BR"},
            RESOURCE_URIS,
            time.monotonic() + 45,
        )
        assert served_pt is not None, (
            "servidor MCP não subiu em 45s; últimos logs:\n" + "".join(logs[-30:])
        )
        for uri in RESOURCE_URIS:
            assert "antes de trabalhar" in served_pt[uri].lower(), (
                f"AC15 violado: {uri} com Accept-Language: pt-BR não serviu prosa "
                f"pt-BR (ausente 'antes de trabalhar'); serviu: "
                f"{served_pt[uri][:120]!r}..."
            )

        # AC15 (hardening) — a TOOL honra o Accept-Language (não só os
        # resources): sem `lang` (nem `ORC_LANG`), o texto servido declara
        # `lang: pt-BR`.
        tool_pt = _http_call_onboarding(
            port, {"Accept-Language": "pt-BR"}, time.monotonic() + 30
        )
        assert tool_pt is not None, (
            "chamada HTTP da tool orc_onboarding com Accept-Language: pt-BR "
            "falhou; últimos logs:\n" + "".join(logs[-30:])
        )
        assert _declares_lang(tool_pt, "pt-BR"), (
            "AC15 violado: tool orc_onboarding com Accept-Language: pt-BR não "
            f"declarou 'lang: pt-BR'; serviu: {tool_pt[:120]!r}..."
        )
        assert "antes de trabalhar" in tool_pt.lower(), (
            "AC15 violado: tool orc_onboarding com Accept-Language: pt-BR "
            "não serviu prosa pt-BR (ausente 'antes de trabalhar')"
        )

        # AC16 — sem header (e sem ORC_LANG) -> prosa en nos três URIs base
        served_en = _http_read_resources(
            port, None, RESOURCE_URIS, time.monotonic() + 30
        )
        assert served_en is not None, (
            "segunda conexão (sem header) falhou; últimos logs:\n" + "".join(logs[-30:])
        )
        for uri in RESOURCE_URIS:
            assert "before working" in served_en[uri].lower(), (
                f"AC16 violado: {uri} sem Accept-Language não serviu prosa en "
                f"(ausente 'before working'); serviu: "
                f"{served_en[uri][:120]!r}..."
            )
    finally:
        _stop_http_server(proc)

    # AC16 (hardening) — ORC_LANG vence o header: servidor com ORC_LANG=en +
    # header Accept-Language: pt-BR serve prosa em inglês.
    proc_env, logs_env = _start_http_server(
        repo, db_file_env, port_env, {"ORC_LANG": "en"}
    )
    try:
        served_env = _http_read_resources(
            port_env,
            {"Accept-Language": "pt-BR"},
            RESOURCE_URIS,
            time.monotonic() + 45,
        )
        assert served_env is not None, (
            "servidor com ORC_LANG=en não subiu em 45s; últimos logs:\n"
            + "".join(logs_env[-30:])
        )
        for uri in RESOURCE_URIS:
            assert "before working" in served_env[uri].lower(), (
                f"AC16 violado: ORC_LANG=en deve vencer Accept-Language: pt-BR "
                f"em {uri}; serviu: {served_env[uri][:120]!r}..."
            )
    finally:
        _stop_http_server(proc_env)

    # limpeza dos artefatos temporários dos servidores
    for f in (db_file, db_file_env):
        try:
            Path(f).unlink(missing_ok=True)
        except OSError:
            pass
