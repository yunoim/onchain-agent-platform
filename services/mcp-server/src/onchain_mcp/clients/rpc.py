"""JSON-RPC client: a small, read-only facade over web3.py.

Every method here maps to one or two `eth_*` calls that any public endpoint serves.
Nothing in this module can build, sign, or send a transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ens.utils import is_valid_name
from mcp.server.mcpserver.exceptions import ToolError
from web3 import HTTPProvider, Web3

from onchain_mcp.formatting import to_jsonable

# keccak256("Transfer(address,address,uint256)"); verified by a unit test.
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

ERC20_ABI: list[dict[str, Any]] = [
    {
        "name": "name",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
    },
    {
        "name": "symbol",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
    {
        "name": "totalSupply",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

BLOCK_TAGS = {"latest", "earliest", "pending", "safe", "finalized"}


@dataclass(frozen=True)
class TransferLog:
    block_number: int
    tx_hash: str
    log_index: int
    from_address: str
    to_address: str
    raw_amount: int


class RpcClient:
    """Read-only Ethereum access. Construct with `from_url` or inject a Web3 instance for tests."""

    def __init__(self, w3: Web3, *, max_log_block_range: int = 2000) -> None:
        self._w3 = w3
        self.max_log_block_range = max_log_block_range

    @classmethod
    def from_url(
        cls, url: str, *, timeout: float = 20.0, max_log_block_range: int = 2000
    ) -> RpcClient:
        provider = HTTPProvider(url, request_kwargs={"timeout": timeout})
        return cls(Web3(provider), max_log_block_range=max_log_block_range)

    # ---- addresses -------------------------------------------------------------------

    def resolve_address(self, name_or_address: str) -> str:
        """Accept a hex address or an ENS name; return a checksummed address."""
        candidate = name_or_address.strip()
        if Web3.is_address(candidate):
            return Web3.to_checksum_address(candidate)
        if "." in candidate and is_valid_name(candidate):
            resolved = self._call(lambda: self._w3.ens.address(candidate))
            if not resolved:
                raise ToolError(f"ENS name '{candidate}' does not resolve to an address")
            return Web3.to_checksum_address(resolved)
        raise ToolError(
            f"'{name_or_address}' is neither a valid hex address nor an ENS name (e.g. vitalik.eth)"
        )

    # ---- state queries ---------------------------------------------------------------

    def get_balance_wei(self, address: str) -> int:
        return int(self._call(lambda: self._w3.eth.get_balance(address)))

    def latest_block_number(self) -> int:
        return int(self._call(lambda: self._w3.eth.block_number))

    def chain_id(self) -> int:
        return int(self._call(lambda: self._w3.eth.chain_id))

    def get_block(self, number_or_tag: int | str) -> dict[str, Any]:
        ident = _normalise_block_identifier(number_or_tag)
        block = self._call(lambda: self._w3.eth.get_block(ident, full_transactions=False))
        data = to_jsonable(block)
        txs = data.get("transactions") or []
        return {
            "number": data.get("number"),
            "hash": data.get("hash"),
            "parent_hash": data.get("parentHash"),
            "timestamp": data.get("timestamp"),
            "miner": data.get("miner"),
            "gas_used": data.get("gasUsed"),
            "gas_limit": data.get("gasLimit"),
            "base_fee_per_gas_wei": data.get("baseFeePerGas"),
            "transaction_count": len(txs),
        }

    def get_transaction(self, tx_hash: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Return (transaction, receipt). Receipt is None while the tx is still pending."""
        tx = to_jsonable(self._call(lambda: self._w3.eth.get_transaction(tx_hash)))
        receipt: dict[str, Any] | None
        try:
            receipt = to_jsonable(self._w3.eth.get_transaction_receipt(tx_hash))
        except Exception:  # noqa: BLE001 - pending tx has no receipt; anything else -> None too
            receipt = None
        return tx, receipt

    def gas_snapshot(self) -> dict[str, int | None]:
        gas_price = int(self._call(lambda: self._w3.eth.gas_price))
        latest = self._call(lambda: self._w3.eth.get_block("latest", full_transactions=False))
        base_fee = latest.get("baseFeePerGas")
        try:
            priority = int(self._w3.eth.max_priority_fee)
        except Exception:  # noqa: BLE001 - not every endpoint supports eth_maxPriorityFeePerGas
            priority = None
        return {
            "gas_price_wei": gas_price,
            "base_fee_per_gas_wei": int(base_fee) if base_fee is not None else None,
            "max_priority_fee_per_gas_wei": priority,
            "block_number": int(latest["number"]),
        }

    # ---- ERC-20 ----------------------------------------------------------------------

    def erc20_metadata(self, contract_address: str) -> dict[str, Any]:
        code = self._call(lambda: self._w3.eth.get_code(contract_address))
        if len(code) == 0:
            raise ToolError(f"{contract_address} has no contract code; it is not a token contract")
        contract = self._w3.eth.contract(address=contract_address, abi=ERC20_ABI)
        return {
            "name": _optional_call(lambda: contract.functions.name().call()),
            "symbol": _optional_call(lambda: contract.functions.symbol().call()),
            "decimals": int(self._call(lambda: contract.functions.decimals().call())),
            "total_supply_raw": int(self._call(lambda: contract.functions.totalSupply().call())),
        }

    def erc20_balance_raw(self, contract_address: str, holder: str) -> int:
        contract = self._w3.eth.contract(address=contract_address, abi=ERC20_ABI)
        return int(self._call(lambda: contract.functions.balanceOf(holder).call()))

    def erc20_decimals(self, contract_address: str) -> int:
        contract = self._w3.eth.contract(address=contract_address, abi=ERC20_ABI)
        return int(self._call(lambda: contract.functions.decimals().call()))

    def transfer_logs(
        self, contract_address: str, from_block: int, to_block: int
    ) -> list[TransferLog]:
        """Fetch ERC-20 Transfer events. The block range is clamped to `max_log_block_range`."""
        if to_block - from_block + 1 > self.max_log_block_range:
            from_block = to_block - self.max_log_block_range + 1
        raw_logs = self._call(
            lambda: self._w3.eth.get_logs(
                {
                    "address": contract_address,
                    "fromBlock": from_block,
                    "toBlock": to_block,
                    "topics": [TRANSFER_TOPIC],
                }
            )
        )
        out: list[TransferLog] = []
        for log in raw_logs:
            topics = log["topics"]
            if len(topics) != 3:  # non-standard Transfer (e.g. ERC-721 with 4 topics)
                continue
            data = bytes(log["data"])
            out.append(
                TransferLog(
                    block_number=int(log["blockNumber"]),
                    tx_hash=_hex(log["transactionHash"]),
                    log_index=int(log["logIndex"]),
                    from_address=_topic_to_address(topics[1]),
                    to_address=_topic_to_address(topics[2]),
                    raw_amount=int.from_bytes(data, "big") if data else 0,
                )
            )
        return out

    # ---- internals -------------------------------------------------------------------

    @staticmethod
    def _call(fn: Any) -> Any:
        """Run one RPC call and convert transport failures into a ToolError the LLM can read."""
        try:
            return fn()
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"RPC request failed: {type(exc).__name__}: {exc}") from exc


def _optional_call(fn: Any) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001 - some tokens return bytes32 or revert on name()/symbol()
        return None


def _normalise_block_identifier(value: int | str) -> int | str:
    if isinstance(value, int):
        if value < 0:
            raise ToolError("block number must be >= 0")
        return value
    text = value.strip().lower()
    if text in BLOCK_TAGS:
        return text
    if text.startswith("0x"):
        return int(text, 16)
    if text.isdigit():
        return int(text)
    raise ToolError(f"'{value}' is not a block number or one of {sorted(BLOCK_TAGS)}")


def _hex(value: Any) -> str:
    if isinstance(value, bytes | bytearray):
        return "0x" + bytes(value).hex()
    text = str(value)
    return text if text.startswith("0x") else "0x" + text


def _topic_to_address(topic: Any) -> str:
    return Web3.to_checksum_address("0x" + _hex(topic)[-40:])
