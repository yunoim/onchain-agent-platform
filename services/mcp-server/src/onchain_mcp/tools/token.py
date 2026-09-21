"""ERC-20 tools: token metadata and recent large transfers scanned from event logs."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from onchain_mcp.formatting import format_units, parse_units
from onchain_mcp.metrics import instrumented
from onchain_mcp.state import state_from

DEFAULT_TRANSFER_LIMIT = 20
MAX_TRANSFER_LIMIT = 100


def register(server: MCPServer) -> None:
    @server.tool()
    @instrumented
    def get_erc20_token_info(contract_address: str, ctx: Context) -> dict[str, Any]:
        """Get metadata for an ERC-20 token contract: name, symbol, decimals, total supply.

        Args:
            contract_address: Token contract address (hex or ENS name).

        Total supply is returned both raw and in human units.
        """
        state = state_from(ctx)
        contract = state.rpc.resolve_address(contract_address)
        meta = state.rpc.erc20_metadata(contract)
        decimals = meta["decimals"]
        return {
            "contract_address": contract,
            "name": meta["name"],
            "symbol": meta["symbol"],
            "decimals": decimals,
            "total_supply": format_units(meta["total_supply_raw"], decimals),
            "total_supply_raw": meta["total_supply_raw"],
        }

    @server.tool()
    @instrumented
    def get_recent_token_transfers(
        contract_address: str,
        ctx: Context,
        blocks: int = 500,
        min_amount: str = "0",
        limit: int = DEFAULT_TRANSFER_LIMIT,
    ) -> dict[str, Any]:
        """Find recent ERC-20 Transfer events for a token, optionally only large ones.

        Scans the last `blocks` blocks (about 12 seconds each; 500 blocks is roughly
        100 minutes; hard-capped at 2000 blocks) and returns transfers with amount >=
        `min_amount`, largest first.

        Args:
            contract_address: Token contract (e.g. USDC 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48).
            blocks: How many recent blocks to scan (1..2000).
            min_amount: Minimum amount in human token units, e.g. "1000000" for one million
                USDC. "0" returns everything.
            limit: Maximum number of transfers to return (1..100).
        """
        state = state_from(ctx)
        if blocks < 1:
            raise ToolError("blocks must be >= 1")
        blocks = min(blocks, state.settings.max_log_block_range)
        limit = max(1, min(limit, MAX_TRANSFER_LIMIT))

        contract = state.rpc.resolve_address(contract_address)
        decimals = state.rpc.erc20_decimals(contract)
        try:
            threshold_raw = parse_units(min_amount, decimals)
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"min_amount '{min_amount}' is not a number") from exc

        to_block = state.rpc.latest_block_number()
        from_block = max(0, to_block - blocks + 1)
        logs = state.rpc.transfer_logs(contract, from_block, to_block)

        matching = [log for log in logs if log.raw_amount >= threshold_raw]
        matching.sort(key=lambda log: log.raw_amount, reverse=True)
        top = matching[:limit]
        return {
            "contract_address": contract,
            "decimals": decimals,
            "from_block": from_block,
            "to_block": to_block,
            "blocks_scanned": to_block - from_block + 1,
            "total_transfers_in_range": len(logs),
            "matching_transfers": len(matching),
            "returned": len(top),
            "min_amount": min_amount,
            "transfers": [
                {
                    "block_number": log.block_number,
                    "tx_hash": log.tx_hash,
                    "from": log.from_address,
                    "to": log.to_address,
                    "amount": format_units(log.raw_amount, decimals),
                    "amount_raw": log.raw_amount,
                }
                for log in top
            ],
        }
