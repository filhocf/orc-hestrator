"""Dependency-pin lock tests (G6) — guard the wheel METADATA, not the checkout.

The checkout's ``uv.lock`` pins ``mcp 1.27.0`` so all 268 tests pass locally.
That pin is NOT in the wheel METADATA: a clean install (``pip install
orc-hestrator-server``) resolves ``mcp 2.x`` (currently 2.3.0), where
``mcp.server.fastmcp`` no longer exists (FastMCP was renamed to MCPServer).
Every entry point dies at import with ``ModuleNotFoundError``.

These tests assert properties of the *installed* distribution metadata so a
regression in ``pyproject.toml`` surfaces immediately without a clean-install
verification step.
"""

import importlib.metadata

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

DIST_NAME = "orc-hestrator-server"


def _find_mcp_requirement() -> str:
    """Return the raw requires-string for the ``mcp`` dependency.

    Raises
    ------
    AssertionError
        If no requirement named ``mcp`` exists in the distribution metadata.
    """
    for req_str in importlib.metadata.requires(DIST_NAME) or []:
        if canonicalize_name(Requirement(req_str).name) == "mcp":
            return req_str
    raise AssertionError(
        f"No requirement named 'mcp' in requires() for {DIST_NAME!r}.\n"
        "Was the dependency removed or renamed?"
    )


def test_mcp_requirement_has_major_upper_bound() -> None:
    """Lock the major upper bound on ``mcp`` (P0 from G6).

    The requirement MUST exclude the 2.x line.  Without a ``<2`` cap a clean
    install resolves ``mcp 2.x`` (e.g. 2.3.0) where ``mcp.server.fastmcp``
    does not exist — ``FastMCP`` was renamed to ``MCPServer`` and the
    ``fastmcp`` submodule was removed.  Every entry point of this package
    crashes with ``ModuleNotFoundError`` at import time.

    The checkout hides this defect: ``uv.lock`` pins ``mcp 1.27.0``, but that
    pin never makes it into the wheel METADATA.  Fix: add ``<2`` to the mcp
    dependency in ``pyproject.toml`` (e.g. ``"mcp>=1.0.0,<2"``).
    """
    raw = _find_mcp_requirement()
    req = Requirement(raw)

    assert Version("2.0.0") not in req.specifier, (
        f"mcp requirement {raw!r} has no major upper bound "
        f"(spec={req.specifier!r}).\n"
        f"DAMAGE: a clean install (pip/uvx) resolves mcp 2.x (e.g. 2.3.0) "
        f"where mcp.server.fastmcp does not exist (FastMCP was renamed to "
        f"MCPServer). ALL entry points die at import with "
        f"ModuleNotFoundError. The checkout uv.lock pins mcp 1.27.0, hiding "
        f"the defect, but that pin is not in the wheel METADATA.\n"
        f"FIX: add <2 to the mcp dependency in pyproject.toml, e.g. "
        f"'mcp>=1.0.0,<2'."
    )


def test_core_install_declares_http_extra_gap() -> None:
    """Lock the core vs. ``ui``-extra boundary for the streamable-http path.

    The ``orc-serve`` entry point (streamable-http transport) requires
    FastAPI, which lives in the optional ``ui`` extra — NOT in core
    dependencies.  A plain ``pip install orc-hestrator-server`` (or
    ``uvx orc-hestrator-server``) does NOT pull in FastAPI; the http server
    will fail at import.

    Consequence (documented): the correct invocation is::

        uvx --from 'orc-hestrator-server[ui]' orc-serve

    This test exists so that moving ``fastapi`` into core dependencies — or
    removing it from the ``ui`` extra — requires a conscious packaging
    decision and a doc update, not a silent break.
    """
    all_requires = importlib.metadata.metadata(DIST_NAME).get_all("Requires-Dist") or []

    core_names: set[str] = set()
    ui_names: set[str] = set()

    for req_str in all_requires:
        req = Requirement(req_str)
        name = canonicalize_name(req.name)
        if req.marker is not None:
            # packaging normalises the marker to double-quoted form.
            if 'extra == "ui"' in str(req.marker):
                ui_names.add(name)
        else:
            # No marker → core dependency.
            core_names.add(name)

    assert "fastapi" not in core_names, (
        "fastapi is in CORE dependencies — this changes the install contract.\n"
        "The streamable-http path (orc-serve) was designed to require the "
        "`ui` extra, so a plain install does NOT pull in FastAPI.\n"
        "If you intentionally promoted fastapi to core, update the "
        "onboarding docs (uvx --from 'orc-hestrator-server[ui]' orc-serve) "
        "and this test together."
    )
    assert "fastapi" in ui_names, (
        "fastapi is NOT in the `ui` extra — the streamable-http path "
        "(orc-serve) will break on clean installs.\n"
        "Correct invocation: uvx --from 'orc-hestrator-server[ui]' orc-serve"
    )
