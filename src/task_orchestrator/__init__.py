"""orc-hestrator-server — MCP server for AI agent work management."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Fonte única: a versão instalada. Antes era um literal que ficou em 0.8.0
    # por dez releases, enquanto o pacote ia a 2.0.1 — resíduo que ninguém vê
    # porque o serverInfo já lia a metadata.
    __version__ = version("orc-hestrator-server")
except PackageNotFoundError:  # rodando de um checkout sem install
    __version__ = "2.2.1"
