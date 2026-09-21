"""Address-history tools backed by Etherscan V2 (optional tier, ADR-0002)."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from onchain_mcp.clients.etherscan import MISSING_KEY_MESSAGE, EtherscanClient
from onchain_mcp.formatting import format_units, wei_to_eth
from onchain_mcp.metrics import instrumented
from onchain_mcp.state import AppState, state_from

DEFAULT_LIMIT = 10


def register(server: MCPServer) -> None:
    @server.tool()
    @instrumented
    def get_address_transactions(
        address: str, ctx: Context, limit: int = DEFAULT_LIMIT
    ) -> dict[str, Any]:
        """List the most recent normal (external) transactions sent to or from an address.

        Requires ETHERSCAN_API_KEY on the server; returns a clear error otherwise.

        Args:
            address: Hex address or ENS name.
            limit: Number of transactions, newest first (1..100).

        Each item has hash, block, timestamp, from, to, value in ETH, gas used, whether it
        failed, and the decoded function name when Etherscan knows the ABI.
        """
        state = state_from(ctx)
        client = _require_etherscan(state)
        resolved = state.rpc.resolve_address(address)
        limit = _clamp(limit, state)
        rows = client.address_transactions(resolved, limit=limit)
        for row in rows:
            wei = row.get("value_wei") or 0
            row["value_eth"] = wei_to_eth(wei)
            row["direction"] = _direction(resolved, row.get("from"), row.get("to"))
        return {
            "address": resolved,
            "count": len(rows),
            "source": "etherscan",
            "transactions": rows,
        }

    @server.tool()
    @instrumented
    def get_address_token_transfers(
        address: str,
        ctx: Context,
        limit: int = DEFAULT_LIMIT,
        contract_address: str | None = None,
    ) -> dict[str, Any]:
        """List the most recent ERC-20 token transfers involving an address.

        Requires ETHERSCAN_API_KEY on the server; returns a clear error otherwise.

        Args:
            address: Hex address or ENS name.
            limit: Number of transfers, newest first (1..100).
            contract_address: Optional token contract to filter on.

        Each item has token name/symbol, amount in human units, counterparties and block.
        """
        state = state_from(ctx)
        client = _require_etherscan(state)
        resolved = state.rpc.resolve_address(address)
        contract = state.rpc.resolve_address(contract_address) if contract_address else None
        limit = _clamp(limit, state)
        rows = client.address_token_transfers(resolved, limit=limit, contract_address=contract)
        for row in rows:
            decimals = row.get("token_decimals") or 0
            raw = row.get("value_raw") or 0
            row["value"] = format_units(raw, decimals)
            row["direction"] = _direction(resolved, row.get("from"), row.get("to"))
        return {
            "address": resolved,
            "contract_filter": contract,
            "count": len(rows),
            "source": "etherscan",
            "transfers": rows,
        }


def _require_etherscan(state: AppState) -> EtherscanClient:
    if state.etherscan is None:
        raise ToolError(MISSING_KEY_MESSAGE)
    return state.etherscan


def _clamp(limit: int, state: AppState) -> int:
    return max(1, min(limit, state.settings.max_history_items))


def _direction(me: str, sender: str | None, recipient: str | None) -> str:
    me_l = me.lower()
    s = (sender or "").lower()
    r = (recipient or "").lower()
    if s == me_l and r == me_l:
        return "self"
    if s == me_l:
        return "out"
    if r == me_l:
        return "in"
    return "other"
