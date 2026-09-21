"""MCP server assembly and CLI entry point.

One server, two transports (ADR-0003):

    onchain-mcp                          # stdio, for Claude Desktop and local smoke tests
    onchain-mcp --transport streamable-http --host 0.0.0.0 --port 8000   # in containers
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from onchain_mcp import __version__
from onchain_mcp.config import Settings
from onchain_mcp.state import AppState
from onchain_mcp.tools import register_all

SERVER_NAME = "onchain-mcp"

INSTRUCTIONS = """\
Read-only Ethereum mainnet data. Tools never sign or send anything.
Addresses may be given as hex or ENS names (e.g. vitalik.eth).
State tools (balances, blocks, gas, transactions, token info, recent transfers) use a
public JSON-RPC node. Address-history tools use Etherscan and need an API key on the
server; if they return a key error, answer with the state tools instead.
Amounts are returned as exact decimal strings; do not re-derive them from raw wei.
"""

StateFactory = Callable[[Settings], AppState]


def build_server(
    settings: Settings | None = None, state_factory: StateFactory | None = None
) -> MCPServer:
    """Create the MCP server. `state_factory` lets tests inject fake clients."""
    settings = settings or Settings()
    factory = state_factory or AppState.from_settings

    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[AppState]:
        state = factory(settings)
        try:
            yield state
        finally:
            state.close()

    server = MCPServer(
        SERVER_NAME,
        title="On-chain read-only tools",
        instructions=INSTRUCTIONS,
        version=__version__,
        lifespan=lifespan,
        log_level=settings.log_level.upper(),  # type: ignore[arg-type]
    )
    register_all(server)
    _register_http_routes(server)
    return server


def _register_http_routes(server: MCPServer) -> None:
    """Liveness and metrics endpoints, mounted only when serving over HTTP."""

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": SERVER_NAME, "version": __version__})

    @server.custom_route("/metrics", methods=["GET"], include_in_schema=False)
    async def metrics(_request: Request) -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="onchain-mcp", description="Read-only Ethereum MCP server"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="stdio for local clients such as Claude Desktop; streamable-http for network use",
    )
    parser.add_argument(
        "--host", default=None, help="HTTP bind host (default: MCP_HOST or 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="HTTP port (default: MCP_PORT or 8000)"
    )
    args = parser.parse_args(argv)

    settings = Settings()
    # stdio uses stdout for protocol frames; logs must go to stderr.
    logging.basicConfig(level=settings.log_level.upper(), stream=sys.stderr)
    server = build_server(settings)

    if args.transport == "stdio":
        server.run(transport="stdio")
        return

    host = args.host or settings.mcp_host
    port = args.port or settings.mcp_port
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=settings.mcp_dns_rebinding_protection,
    )
    logging.getLogger(SERVER_NAME).info("serving streamable-http on http://%s:%d/mcp", host, port)
    server.run(
        transport="streamable-http",
        host=host,
        port=port,
        stateless_http=settings.mcp_stateless,
        json_response=True,
        transport_security=security,
    )


if __name__ == "__main__":
    main()
