"""RED tests (G3) — fatia F7: variáveis de ambiente primárias ``ORC_*`` (R3).

A fatia F7 promove ``ORC_DB``/``ORC_CONFIG`` a primárias, mantém
``TASK_ORCHESTRATOR_DB``/``TASK_ORCHESTRATOR_CONFIG`` como fallback e exige um
AVISO ÚNICO de deprecação no log que nomeie a variável nova. Quatro testes:

- ``test_orc_db_wins_over_legacy_by_execution`` — por EXECUÇÃO: sobe ``orc``
  em stdio com ``ORC_DB`` e ``TASK_ORCHESTRATOR_DB`` apontando para dois
  arquivos distintos e prova qual arquivo foi criado (o de ``ORC_DB``) e que
  o legado NÃO existe (AC3).
- ``test_orc_config_wins_over_legacy`` — in-process: ``schemas.resolve_config_path()``
  (função pública nova) lê ``ORC_CONFIG``, cai para ``TASK_ORCHESTRATOR_CONFIG``
  e devolve ``None`` se nenhuma.
- ``test_legacy_env_emits_single_deprecation`` — in-process: só
  ``TASK_ORCHESTRATOR_DB`` definida; ``db.resolve_db_path()`` chamada duas vezes
  emite EXATAMENTE UM aviso (no log) mencionando ``ORC_DB`` (R3: aviso único).
- ``test_resolve_db_path_default_is_o
rc_home`` — in-process: sem nenhuma var,
  ``db.resolve_db_path()`` devolve o default prometido no README,
  ``~/.orc/tasks.db`` (expandido).

Os três in-process falham hoje porque ``resolve_config_path`` e ``resolve_db_path``
ainda não existem (o resolvedor ORC_* -> legado -> default não foi implementado);
o de execução falha porque o script ``orc`` ainda não existe e o código lê o
legado. Os helpers (spawn stdio) ficam NESTE arquivo, por convenção do repo.
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path

_REPO = str(Path(__file__).resolve().parents[1])
# Orçamento por execução stdio (generoso, como pedido; o retry sai cedo se o
# comando não existir — falhas rápidas repetidas — ou se o servidor responde).
_DEADLINE_S = 40.0


def _spawn_stdio(script: str, env_extra: dict[str, str], deadline: float):
    """Spawna ``uv run <script>`` via cliente MCP stdio oficial, faz
    ``initialize``, captura o ``stderr`` (via ``errlog``) e devolve
    ``(init_result_or_None, stderr_text)``.

    O processo-grupo é morto pelo próprio ``stdio_client`` no teardown
    (``start_new_session=True`` + ``os.killpg`` do SDK). O retry sai cedo após
    falhas rápidas repetidas (comando não existe) para não queimar o deadline.
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
            # Falha rápida repetida => comando não existe; não adianta retriar.
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


def test_orc_db_wins_over_legacy_by_execution(tmp_path):
    """AC3: ``ORC_DB`` vence ``TASK_ORCHESTRATOR_DB`` quando ambos existem.

    Comportamento travado (por execução, com dois bancos distintos): com
    ``ORC_DB`` e ``TASK_ORCHESTRATOR_DB`` apontando para dois arquivos
    distintos em ``tmp_path``, sobe ``orc`` em stdio via cliente MCP oficial e
    prova que o arquivo CRIADO foi o de ``ORC_DB`` e que o legado NÃO foi
    criado. Hoje o script ``orc`` não existe e o código lê o legado — falha.
    """
    orc_db = str(tmp_path / "orc_wins.db")
    legacy_db = str(tmp_path / "legacy.db")

    init, _stderr = _spawn_stdio(
        "orc",
        {"ORC_DB": orc_db, "TASK_ORCHESTRATOR_DB": legacy_db},
        time.monotonic() + _DEADLINE_S,
    )
    assert init is not None, (
        "servidor stdio `orc` não subiu para o handshake MCP "
        f"(deadline {int(_DEADLINE_S)}s)"
    )
    # Dá um instante para o SQLite materializar o arquivo na disk.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if Path(orc_db).exists() or Path(legacy_db).exists():
            break
        time.sleep(0.1)

    assert Path(orc_db).exists(), (
        f"esperava o banco em ORC_DB criado ({orc_db}); o código está usando "
        "a variável errada (R3: ORC_DB é a primária)"
    )
    assert not Path(legacy_db).exists(), (
        f"o banco LEGADO foi criado ({legacy_db}); ORC_DB deveria ter vencido (R3/AC3)"
    )


def test_orc_config_wins_over_legacy(tmp_path, monkeypatch):
    """R3: ``ORC_CONFIG`` vence ``TASK_ORCHESTRATOR_CONFIG`` (in-process).

    Comportamento travado: ``task_orchestrator.schemas.resolve_config_path()``
    (função pública nova) lê ``ORC_CONFIG``, cai para ``TASK_ORCHESTRATOR_CONFIG``
    e devolve ``None`` se nenhuma. Com as duas definidas, devolve o caminho
    novo. Hoje a função não existe — falha.
    """
    from task_orchestrator import schemas

    new_cfg = tmp_path / "orc_config.yaml"
    legacy_cfg = tmp_path / "legacy_config.yaml"
    new_cfg.write_text("work_item_schemas: {}\n")
    legacy_cfg.write_text("work_item_schemas: {}\n")

    monkeypatch.setenv("ORC_CONFIG", str(new_cfg))
    monkeypatch.setenv("TASK_ORCHESTRATOR_CONFIG", str(legacy_cfg))

    resolved = schemas.resolve_config_path()
    assert resolved is not None, (
        "resolve_config_path() deve devolver o caminho do ORC_CONFIG quando "
        "ele está definido"
    )
    assert Path(resolved) == new_cfg, (
        f"esperava o caminho novo {new_cfg}, resolve_config_path() devolveu "
        f"{resolved!r} (R3: ORC_CONFIG é o primário)"
    )


def test_legacy_env_emits_single_deprecation(tmp_path, monkeypatch, caplog):
    """R3: usar a variável LEGADA emite UM único aviso nomando ``ORC_DB``.

    Comportamento travado: apenas ``TASK_ORCHESTRATOR_DB`` definida (sem
    ``ORC_DB``), ``db.resolve_db_path()`` chamada DUAS vezes emite EXATAMENTE
    UM aviso no log mencionando ``ORC_DB`` (aviso único, R3). Hoje a função
    não existe — falha.
    """
    import logging

    from task_orchestrator import db

    legacy_db = str(tmp_path / "legacy.db")
    monkeypatch.setenv("TASK_ORCHESTRATOR_DB", legacy_db)
    monkeypatch.delenv("ORC_DB", raising=False)

    with caplog.at_level(logging.WARNING):
        db.resolve_db_path()
        db.resolve_db_path()

    orc_warnings = [r for r in caplog.records if "ORC_DB" in r.getMessage()]
    assert len(orc_warnings) == 1, (
        f"esperava EXATAMENTE 1 aviso no log mencionando ORC_DB ao usar a "
        f"variável legada, vieram {len(orc_warnings)} "
        "(R3: aviso único de deprecação nomeando o ORC_DB)"
    )


def test_resolve_db_path_default_is_orc_home(tmp_path, monkeypatch):
    """R3/README: sem variáveis, o default é ``~/.orc/tasks.db`` (expandido).

    Comportamento travado: sem ``ORC_DB`` nem ``TASK_ORCHESTRATOR_DB``,
    ``db.resolve_db_path()`` devolve o ``Path`` expandido de ``~/.orc/tasks.db``
    (o default já prometido no README publicado). Hoje a função não existe e o
    default é ``~/.task-orchestrator/tasks.db`` — falha.
    """
    from task_orchestrator import db

    monkeypatch.delenv("ORC_DB", raising=False)
    monkeypatch.delenv("TASK_ORCHESTRATOR_DB", raising=False)

    expected = Path.home() / ".orc" / "tasks.db"
    resolved = db.resolve_db_path()
    assert resolved is not None, (
        "resolve_db_path() deve devolver o default quando não há variáveis"
    )
    assert Path(resolved).expanduser() == expected, (
        f"esperava o default {expected}, resolve_db_path() devolveu "
        f"{resolved!r} (R3/README: default ORC_HOME é ~/.orc/tasks.db)"
    )
