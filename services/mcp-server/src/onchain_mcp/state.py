"""Per-process application state, created once in the server lifespan and handed to tools."""

from __future__ import annotations

from dataclasses import dataclass

from mcp.server.mcpserver import Context

from onchain_mcp.clients.etherscan import EtherscanClient
from onchain_mcp.clients.rpc import RpcClient
from onchain_mcp.config import Settings


@dataclass
class AppState:
    settings: Settings
    rpc: RpcClient
    etherscan: EtherscanClient | None
    """None when ETHERSCAN_API_KEY is empty; history tools then fail with a clear message."""

    @classmethod
    def from_settings(cls, settings: Settings) -> AppState:
        rpc = RpcClient.from_url(
            settings.eth_rpc_url,
            timeout=settings.request_timeout_seconds,
            max_log_block_range=settings.max_log_block_range,
        )
        etherscan = (
            EtherscanClient(
                settings.etherscan_api_key,
                chain_id=settings.chain_id,
                base_url=settings.etherscan_base_url,
                timeout=settings.request_timeout_seconds,
            )
            if settings.etherscan_api_key
            else None
        )
        return cls(settings=settings, rpc=rpc, etherscan=etherscan)

    def close(self) -> None:
        if self.etherscan is not None:
            self.etherscan.close()


def state_from(ctx: Context) -> AppState:
    """Fetch the AppState the lifespan yielded. Tools call this instead of using globals."""
    return ctx.request_context.lifespan_context
