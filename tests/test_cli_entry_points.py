"""RED tests (G3/G5.1) — fatia F7: pontos de entrada / transporte (R2, R10, ADR-007).

Quatro testes: os três primeiros por EXECUÇÃO REAL (cliente MCP oficial; o
processo-grupo é morto pelo próprio ``stdio_client`` no teardown —
``start_new_session=True`` + ``os.killpg`` do SDK); o último apenas inspeciona
o ambiente, sem subir servidor:

- ``test_orc_runs_stdio_without_transport_env`` — ``uv run orc`` SEM
  ``MCP_TRANSPORT`` sobe em stdio e o cliente inicializa e obtém ``serverInfo``
  (prova ADR-007/AC8: o transporte vem do ponto de entrada, não do env).
- ``test_orc_serve_uses_mcp_port`` — ``uv run orc-serve`` SEM ``MCP_TRANSPORT``
  sobe em streamable-http na porta definida em ``MCP_PORT``.
- ``test_legacy_script_emits_one_deprecation_and_orc_mcp_does_not`` — o alias
  legado ``task-orchestrator-py`` emite UMA linha de deprecação no stderr
  mencionando o comando novo; ``orc-mcp`` (alias stdio sem aviso) NÃO emite
  (AC2/R2).
- ``test_distribution_homonym_script_exists`` — o console script
  ``orc-hestrator-server`` (homônimo da distribuição) está instalado e é
  resolúvel, porque ``uvx <distribuição>`` só funciona com script homônimo
  (R2.1/P1-2 do G5).

Os três testes de execução real passam desde o G4 GREEN; o do script
homônimo é o RED do G5.1 — falha hoje porque nenhum script homônimo à
distribuição foi criado no G4.
"""

import asyncio
import importlib.metadata
import os
import shutil
import socket
import tempfile
import time
from pathlib import Path

_REPO = str(Path(__file__).resolve().parents[1])
# Orçamento generoso (pedido). O retry de stdio sai cedo em falhas rápidas
# repetidas (comando inexistente); o de HTTP sai cedo se o processo morrer.
_STDIO_DEADLINE_S = 40.0
_HTTP_DEADLINE_S = 45.0


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _spawn_stdio(script: str, env_extra: dict[str, str], deadline: float):
    """Spawna ``uv run <script>`` via cliente MCP stdio oficial, faz
    ``initialize``, captura o ``stderr`` (via ``errlog``) e devolve
    ``(init_result_or_None, stderr_text)``. O processo-grupo é morto pelo SDK
    no teardown. Sai cedo após falhas rápidas repetidas (comando inexistente).
    """
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    fd, err_path = tempfile.mkstemp(prefix="orc_stderr_")
    errlog = os.fdopen(fd, "w", encoding="utf-8")
    env = {**os.environ, **env_extra}

    async def _attempt():
        params = StdioServerParameters(
            command="uv", args=["run", script], env=env, cwd=_REPO
        )
        async with stdio_client(params, errlog=errlog) as (r, w):  # noqa: SIM117
            async with ClientSession(r, w) as session:
                return await session.initialize()

    result = None
    fast_fails = 0
    while time.monotonic() < deadline:
        t0 = time.monotonic()
        try:
            result = asyncio.run(_attempt())
            break
        except Exception:
            if time.monotonic() - t0 < 2.0:
                fast_fails += 1
                if fast_fails >= 3:
                    break
            time.sleep(0.5)

    errlog.flush()
    errlog.close()
    with open(err_path, encoding="utf-8", errors="replace") as f:
        stderr_text = f.read()
    os.unlink(err_path)
    return result, stderr_text


def _run_stdio_initialize(script: str, env_extra: dict[str, str], deadline: float):
    """Apenas o ``initialize`` (sem capturar stderr) para os testes de transporte."""
    init, _ = _spawn_stdio(script, env_extra, deadline)
    return init


def _run_http_initialize(port: int, deadline: float, proc=None):
    """Handshake streamable-http oficial; devolve o resultado (ou None)."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _attempt():
        # SIM117 desligado: ClientSession depende de (r, w) do context manager
        # externo, e os dois são async: não cabem num único `with`.
        async with streamablehttp_client(f"http://127.0.0.1:{port}/mcp") as (r, w, _):  # noqa: SIM117
            async with ClientSession(r, w) as session:
                return await session.initialize()

    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            break  # servidor morreu: não adianta retriar
        try:
            return asyncio.run(_attempt())
        except Exception:
            time.sleep(0.5)
    return None


def _start_http_server(db_file: str, port: int):
    """Sobe ``uv run orc-serve`` (transporte pelo entry point, sem
    ``MCP_TRANSPORT``) com banco isolado em tmp_path. Devolve ``(proc, logs)``.
    """
    import subprocess
    import threading

    logs: list[str] = []

    def _reader(proc):
        assert proc.stdout is not None
        for line in proc.stdout:
            logs.append(line.decode(errors="replace"))
            if len(logs) > 500:
                del logs[:250]

    env = {
        **os.environ,
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": str(port),
        "ORC_DB": db_file,
        "TASK_ORCHESTRATOR_DB": db_file,  # defensivo: nunca tocar o DB real
    }
    env.pop("MCP_TRANSPORT", None)  # ADR-007: orc-serve decide pelo entry point
    proc = subprocess.Popen(
        ["uv", "run", "orc-serve"],
        cwd=_REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    threading.Thread(target=_reader, args=(proc,), daemon=True).start()
    return proc, logs


def _stop_http_server(proc) -> None:
    import signal

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()
    proc.wait(timeout=10)


def test_orc_runs_stdio_without_transport_env(tmp_path):
    """AC8/ADR-007: ``orc`` sobe em stdio SEM ``MCP_TRANSPORT``.

    Comportamento travado: spawna ``uv run orc`` com ``MCP_TRANSPORT`` REMOVIDO
    do env; o cliente MCP stdio oficial inicializa e obtém ``serverInfo``. O
    transporte vem do ponto de entrada (stdio), não da variável — prova de que
    ``MCP_TRANSPORT`` não é mais o mecanismo em que o deploy confia. Hoje o
    script ``orc`` não existe — falha.
    """
    db_file = str(tmp_path / "orc_stdio.db")
    init = _run_stdio_initialize(
        "orc",
        {
            "ORC_DB": db_file,
            "TASK_ORCHESTRATOR_DB": db_file,  # defensivo: não tocar o DB real
        },
        time.monotonic() + _STDIO_DEADLINE_S,
    )
    assert init is not None, (
        "servidor stdio `orc` não subiu SEM MCP_TRANSPORT para o handshake MCP "
        f"(deadline {int(_STDIO_DEADLINE_S)}s; ADR-007: orc abre em stdio)"
    )
    assert init.serverInfo is not None and init.serverInfo.name, (
        "handshake `orc` (stdio) deveria devolver serverInfo com nome"
    )


def test_orc_serve_uses_mcp_port(tmp_path):
    """AC8/ADR-007: ``orc-serve`` sobe em streamable-http na porta de ``MCP_PORT``.

    Comportamento travado: spawna ``uv run orc-serve`` SEM ``MCP_TRANSPORT`` e
    conecta um cliente streamable-http oficial em ``http://127.0.0.1:<MCP_PORT>``.
    O transporte (HTTP) e a porta vêm do ponto de entrada + ``MCP_PORT`` —
    sem depender de ``MCP_TRANSPORT``. Hoje o script ``orc-serve`` não existe —
    falha.
    """
    db_file = str(tmp_path / "orc_serve.db")
    port = _free_port()
    proc, logs = _start_http_server(db_file, port)
    try:
        init = _run_http_initialize(port, time.monotonic() + _HTTP_DEADLINE_S, proc)
        assert init is not None, (
            "servidor `orc-serve` não subiu em streamable-http na porta "
            f"MCP_PORT={port} SEM MCP_TRANSPORT (deadline "
            f"{int(_HTTP_DEADLINE_S)}s); últimos logs:\n" + "".join(logs[-30:])
        )
        assert init.serverInfo is not None and init.serverInfo.name, (
            "handshake `orc-serve` (http) deveria devolver serverInfo com nome"
        )
    finally:
        _stop_http_server(proc)


def _deprecation_lines(stderr_text: str) -> list[str]:
    """Linhas do stderr que parecem aviso de deprecação (ci).

    'depreca' casa com 'deprecated'/'deprecation' (en) e 'deprecação' (pt-BR).
    """
    return [ln for ln in stderr_text.splitlines() if "depreca" in ln.lower()]


def test_legacy_script_emits_one_deprecation_and_orc_mcp_does_not(tmp_path):
    """AC2/R2: alias legado emite deprecação; ``orc-mcp`` não.

    Comportamento travado: spawna ``uv run task-orchestrator-py`` (alias
    legado, stdio) via cliente MCP e asserta UMA linha de deprecação no stderr
    mencionando o comando novo; depois spawna ``uv run orc-mcp`` (alias stdio
    sem aviso) e asserta que o stderr NÃO tem deprecação. Timeout generoso e
    o processo-grupo é morto no teardown (pelo stdio_client do SDK). Hoje o
    alias legado NÃO emite deprecação e ``orc-mcp`` não existe — falha.
    """
    db_file = str(tmp_path / "alias.db")
    env = {
        "ORC_DB": db_file,
        "TASK_ORCHESTRATOR_DB": db_file,  # defensivo: não tocar o DB real
    }

    # (1) alias legado -> UMA linha de deprecação mencionando o comando novo
    _legacy_init, legacy_stderr = _spawn_stdio(
        "task-orchestrator-py", env, time.monotonic() + _STDIO_DEADLINE_S
    )
    dep = _deprecation_lines(legacy_stderr)
    assert dep, (
        "o alias legado `task-orchestrator-py` deve emitir aviso de "
        f"deprecação em stderr (AC2/R2); stderr capturado: {legacy_stderr[:400]!r}"
    )
    assert any("orc" in ln.lower() for ln in dep), (
        f"a linha de deprecação deve mencionar o comando novo (orc); linhas: {dep!r}"
    )

    # (2) orc-mcp -> alias stdio SEM aviso de deprecação
    _new_init, new_stderr = _spawn_stdio(
        "orc-mcp", env, time.monotonic() + _STDIO_DEADLINE_S
    )
    assert not _deprecation_lines(new_stderr), (
        "`orc-mcp` (alias stdio sem aviso) NÃO deve emitir deprecação; stderr "
        f"capturado: {new_stderr[:400]!r}"
    )


def test_distribution_homonym_script_exists():
    """R2.1/P1-2 (G5): ``uvx orc-hestrator-server`` exige script homônimo.

    ``uvx <distribuição>`` procura um console script com o nome exato da
    distribuição. O quick-start publicado promete ``uvx orc-hestrator-server``,
    mas os scripts criados no G4 são ``orc-hestrator``, ``orc``, ``orc-mcp``,
    ``orc-serve`` e ``orc-ui`` — nenhum homônimo — então o ``uvx`` falha hoje.
    Verifica SEM subir servidor que ``orc-hestrator-server`` está no grupo
    ``console_scripts`` de ``importlib.metadata.entry_points()`` ou é
    resolúvel por ``shutil.which`` (qualquer um dos dois basta para o ``uvx``
    resolver).
    """
    script = "orc-hestrator-server"
    console_scripts = importlib.metadata.entry_points().select(group="console_scripts")
    declared = sorted(ep.name for ep in console_scripts)
    on_path = shutil.which(script)

    assert script in declared or on_path is not None, (
        f"console script homônimo '{script}' não está instalado no ambiente "
        "(R2.1/P1-2: `uvx orc-hestrator-server` não resolve porque nenhum "
        f"script leva o nome da distribuição). console_scripts visíveis: "
        f"{declared}; shutil.which('{script}'): {on_path!r}"
    )
