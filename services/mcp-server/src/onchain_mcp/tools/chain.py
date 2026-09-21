"""Chain-state tools: blocks, gas, and individual transactions."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from onchain_mcp.formatting import wei_to_eth, wei_to_gwei
from onchain_mcp.metrics import instrumented
from onchain_mcp.state import state_from


def register(server: MCPServer) -> None:
    @server.tool()
    @instrumented
    def get_block(ctx: Context, block: str = "latest") -> dict[str, Any]:
        """Get summary information about an Ethereum block.

        Args:
            block: A block number ("19000000"), a hex number ("0x121eac0"), or one of
                "latest", "safe", "finalized", "earliest", "pending". Defaults to "latest".

        Returns number, hash, timestamp (unix seconds), miner, gas used/limit, base fee,
        and how many transactions the block contains. Transaction bodies are not included.
        """
        state = state_from(ctx)
        data = state.rpc.get_block(block)
        base_fee = data.get("base_fee_per_gas_wei")
        data["base_fee_per_gas_gwei"] = wei_to_gwei(base_fee) if base_fee is not None else None
        return data

    @server.tool()
    @instrumented
    def get_gas_price(ctx: Context) -> dict[str, Any]:
        """Get current Ethereum gas prices.

        Returns the legacy gas price, the latest block's base fee, and the node's suggested
        priority fee (tip), each in gwei and wei, plus a simple estimated cost for a plain
        21,000-gas ETH transfer at the current gas price.
        """
        state = state_from(ctx)
        snap = state.rpc.gas_snapshot()
        gas_price = snap["gas_price_wei"] or 0
        priority = snap["max_priority_fee_per_gas_wei"]
        base_fee = snap["base_fee_per_gas_wei"]
        return {
            "block_number": snap["block_number"],
            "gas_price_gwei": wei_to_gwei(gas_price),
            "gas_price_wei": gas_price,
            "base_fee_per_gas_gwei": wei_to_gwei(base_fee) if base_fee is not None else None,
            "max_priority_fee_per_gas_gwei": wei_to_gwei(priority)
            if priority is not None
            else None,
            "simple_transfer_cost_eth": wei_to_eth(gas_price * 21_000),
        }

    @server.tool()
    @instrumented
    def get_transaction(tx_hash: str, ctx: Context) -> dict[str, Any]:
        """Get a transaction by hash, including its receipt when it has been mined.

        Returns sender, recipient, value in ETH, gas details, input calldata (hex), the block
        it was included in, and the receipt status ("success", "reverted", or "pending").
        """
        state = state_from(ctx)
        tx, receipt = state.rpc.get_transaction(tx_hash.strip())
        value_wei = int(tx.get("value") or 0)
        status: str
        if receipt is None:
            status = "pending"
        else:
            status = "success" if int(receipt.get("status") or 0) == 1 else "reverted"
        result: dict[str, Any] = {
            "hash": tx.get("hash"),
            "status": status,
            "block_number": tx.get("blockNumber"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "value_eth": wei_to_eth(value_wei),
            "value_wei": value_wei,
            "nonce": tx.get("nonce"),
            "gas_limit": tx.get("gas"),
            "gas_price_gwei": wei_to_gwei(int(tx["gasPrice"])) if tx.get("gasPrice") else None,
            "input": tx.get("input"),
            "input_length_bytes": _hex_len(tx.get("input")),
        }
        if receipt is not None:
            gas_used = int(receipt.get("gasUsed") or 0)
            effective = int(receipt.get("effectiveGasPrice") or 0)
            result.update(
                {
                    "gas_used": gas_used,
                    "effective_gas_price_gwei": wei_to_gwei(effective),
                    "fee_paid_eth": wei_to_eth(gas_used * effective),
                    "log_count": len(receipt.get("logs") or []),
                    "contract_created": receipt.get("contractAddress"),
                }
            )
        return result


def _hex_len(value: Any) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        return 0
    return (len(value) - 2) // 2
