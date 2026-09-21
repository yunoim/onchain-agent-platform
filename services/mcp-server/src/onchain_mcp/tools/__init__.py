"""Tool registration. Each module exposes `register(server)`; `register_all` wires them up."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from onchain_mcp.tools import account, chain, history, token


def register_all(server: MCPServer) -> None:
    account.register(server)
    chain.register(server)
    token.register(server)
    history.register(server)
