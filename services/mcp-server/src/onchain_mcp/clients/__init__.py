"""Thin clients over the two data tiers (ADR-0002): JSON-RPC for state, Etherscan for history."""

from onchain_mcp.clients.etherscan import EtherscanClient
from onchain_mcp.clients.rpc import RpcClient

__all__ = ["EtherscanClient", "RpcClient"]
