"""Balance tools: native ETH and ERC-20 balances for an address or ENS name."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from onchain_mcp.formatting import format_units, wei_to_eth
from onchain_mcp.metrics import instrumented
from onchain_mcp.state import state_from


def register(server: MCPServer) -> None:
    @server.tool()
    @instrumented
    def get_eth_balance(address: str, ctx: Context) -> dict[str, Any]:
        """Get the native ETH balance of an Ethereum address or ENS name (e.g. "vitalik.eth").

        Returns the resolved checksummed address, the balance in ETH as an exact decimal
        string, the raw balance in wei, and the block number the reading was taken at.
        """
        state = state_from(ctx)
        resolved = state.rpc.resolve_address(address)
        wei = state.rpc.get_balance_wei(resolved)
        return {
            "input": address,
            "address": resolved,
            "balance_eth": wei_to_eth(wei),
            "balance_wei": wei,
            "block_number": state.rpc.latest_block_number(),
        }

    @server.tool()
    @instrumented
    def get_erc20_balance(contract_address: str, address: str, ctx: Context) -> dict[str, Any]:
        """Get an address's balance of a specific ERC-20 token.

        Args:
            contract_address: The token contract (e.g. USDC is
                0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48).
            address: Holder address or ENS name.

        Returns the balance in human units (decimals applied) and the raw integer amount.
        """
        state = state_from(ctx)
        contract = state.rpc.resolve_address(contract_address)
        holder = state.rpc.resolve_address(address)
        decimals = state.rpc.erc20_decimals(contract)
        raw = state.rpc.erc20_balance_raw(contract, holder)
        return {
            "contract_address": contract,
            "address": holder,
            "decimals": decimals,
            "balance": format_units(raw, decimals),
            "balance_raw": raw,
        }
