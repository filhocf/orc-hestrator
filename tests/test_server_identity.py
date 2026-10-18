"""RED tests (G3) — fatia F7: identidade do servidor após a renomeação (AC4/R4).

Ambos os testes são por EXECUÇÃO REAL: sobem o servidor em subprocesso
(``uv run orc-serve``), com porta livre passada em ``MCP_PORT``, banco em
``tmp_path`` (``ORC_DB``, e também ``TASK_ORCHESTRATOR_DB`` apontando para o
mesmo arquivo para o subprocesso NUNCA tocar no banco real do usuário) e um
cliente MCP streamable-http oficial faz o ``initialize``.

Contrato travado (SPEC F7, AC4/R4; ADR-006/ADR-007):

- ``test_server_info_name_is_orc`` — ``initialize`` reporta
  ``serverInfo.name == "orc"`` (hoje o servidor reporta ``"task-orchestrator"``).
- ``test_server_version_matches_new_distribution`` — ``initialize`` reporta
  ``serverInfo.version == importlib.metadata.version("orc-hestrator-server")`` (hoje a
  distribuição ainda se chama ``task-orchestrator-py`` e o script ``orc-serve``
  nem existe).

Os dois DEVEM FALHAR agora (o ``orc-serve`` ainda não existe como console
script e a distribuição ainda é ``task-orchestrator-py``) e viram verdes quando
o G4 GREEN renomear a distribuição, reportar ``name="orc"`` e expor o script.
``orc-serve`` abre em ``streamable-http`` pelo ponto de entrada (ADR-007), por
isso NÃO setamos ``MCP_TRANSPORT``.
"""

import asyncio
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

# Orçamento total por teste: ~45 s (mesmo padrão dos e2e de test_onboarding).
_DEADLINE_S = 45.0


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start_http_server(
    repo: str, db_file: str, port: int
) -> tuple[subprocess.Popen, list[str]]:
    """Sobe ``uv run orc-serve`` em subprocesso (transporte decidido pelo
    ponto de entrada — ADR-007, sem ``MCP_TRANSPORT``).

    O banco é isolado em ``db_file`` (tmp_path): definimos ``ORC_DB`` e, de
    forma defensiva, também ``TASK_ORCHESTRATOR_DB`` apontando para o MESMO
    arquivo, para que nenhuma era do código (hoje lê o legado, depois lê o
    novo) toque no ``~/.task-orchestrator/tasks.db`` real do usuário. Devolve
    ``(proc, logs)`` com os logs capturados em thread.
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
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": str(port),
        "ORC_DB": db_file,
        "TASK_ORCHESTRATOR_DB": db_file,  # defensivo: nunca tocar o DB real
    }
    env.pop("MCP_TRANSPORT", None)  # ADR-007: orc-serve decide pelo entry point
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


def _run_client_initialize(port: int, deadline: float, proc=None):
    """Conectar com o cliente streamable-http oficial e devolver o resultado
    do ``initialize`` (ou None se esgotar o prazo).

    Se ``proc`` for passado e o processo já morreu, sai do loop de retry
    imediatamente (servidor morto não volta a subir).
    """
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


def test_server_info_name_is_orc(tmp_path):
    """AC4/R4: ``initialize`` reporta ``serverInfo.name == "orc"``.

    Comportamento travado: sobe ``orc-serve`` de verdade (porta livre, ORC_DB
    em tmp_path) e um cliente MCP streamable-http oficial faz o handshake. O
    servidor renomeado DEVE reportar o nome ``"orc"`` — não mais o
    ``"task-orchestrator"`` legado. Hoje falha (script inexistente / nome
    antigo). Orçamento ~45 s; teardown garantido no finally.
    """
    repo = str(Path(__file__).resolve().parents[1])
    db_file = str(tmp_path / "identity_name.db")

    port = _free_port()
    proc, logs = _start_http_server(repo, db_file, port)
    try:
        init = _run_client_initialize(port, time.monotonic() + _DEADLINE_S, proc)
        assert init is not None, (
            "servidor MCP (orc-serve) não subiu em "
            f"{int(_DEADLINE_S)}s; últimos logs:\n" + "".join(logs[-30:])
        )
        assert init.serverInfo.name == "orc", (
            f"serverInfo.name={init.serverInfo.name!r} != 'orc' "
            "(AC4/R4: o servidor renomeado reporta name='orc')"
        )
    finally:
        _stop_http_server(proc)


def test_server_version_matches_new_distribution(tmp_path):
    """AC4/R4: ``initialize`` reporta a versão da NOVA distribuição.

    Comportamento travado: sobe ``orc-serve`` de verdade (porta livre, ORC_DB
    em tmp_path) e um cliente MCP streamable-http oficial compara
    ``init.serverInfo.version`` com
    ``importlib.metadata.version("orc-hestrator-server")``. Hoje a distribuição ainda
    se chama ``task-orchestrator-py`` e o script ``orc-serve`` não existe —
    ambos os motivos tornam este teste vermelho. Orçamento ~45 s; teardown
    garantido no finally.
    """
    from importlib.metadata import version as pkg_version

    repo = str(Path(__file__).resolve().parents[1])
    db_file = str(tmp_path / "identity_version.db")

    port = _free_port()
    proc, logs = _start_http_server(repo, db_file, port)
    try:
        init = _run_client_initialize(port, time.monotonic() + _DEADLINE_S, proc)
        assert init is not None, (
            "servidor MCP (orc-serve) não subiu em "
            f"{int(_DEADLINE_S)}s; últimos logs:\n" + "".join(logs[-30:])
        )
        expected = pkg_version("orc-hestrator-server")
        assert init.serverInfo.version == expected, (
            f"serverInfo.version={init.serverInfo.version!r} != "
            f"versão da distribuição orc-hestrator-server {expected!r} "
            "(AC4/R4: deve vir de importlib.metadata da distribuição nova)"
        )
    finally:
        _stop_http_server(proc)
