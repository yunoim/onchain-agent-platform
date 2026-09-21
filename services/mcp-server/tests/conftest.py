"""Shared fixtures: a duck-typed fake Web3 so no test touches the network."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from hexbytes import HexBytes
from web3.datastructures import AttributeDict

from onchain_mcp.clients.rpc import RpcClient
from onchain_mcp.config import Settings
from onchain_mcp.state import AppState

VITALIK = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
HOLDER_A = "0x1111111111111111111111111111111111111111"
HOLDER_B = "0x2222222222222222222222222222222222222222"
TX_HASH = "0x" + "ab" * 32


def topic_for(address: str) -> HexBytes:
    return HexBytes("0x" + "00" * 12 + address[2:].lower())


def make_transfer_log(
    *, block: int, index: int, sender: str, recipient: str, amount: int
) -> AttributeDict:
    return AttributeDict(
        {
            "address": USDC,
            "blockNumber": block,
            "logIndex": index,
            "transactionHash": HexBytes(f"0x{block:064x}"),
            "topics": [
                HexBytes("0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"),
                topic_for(sender),
                topic_for(recipient),
            ],
            "data": HexBytes(amount.to_bytes(32, "big")),
        }
    )


class _FakeFunction:
    def __init__(self, value: Any) -> None:
        self._value = value

    def call(self) -> Any:
        if isinstance(self._value, Exception):
            raise self._value
        return self._value


class _FakeFunctions:
    """Mimics `contract.functions.<name>(args).call()` for the ERC-20 ABI subset."""

    def __init__(self, token: dict[str, Any], balances: dict[str, int]) -> None:
        self._token = token
        self._balances = balances

    def name(self) -> _FakeFunction:
        return _FakeFunction(self._token["name"])

    def symbol(self) -> _FakeFunction:
        return _FakeFunction(self._token["symbol"])

    def decimals(self) -> _FakeFunction:
        return _FakeFunction(self._token["decimals"])

    def totalSupply(self) -> _FakeFunction:  # noqa: N802 - mirrors Solidity ABI name
        return _FakeFunction(self._token["total_supply"])

    def balanceOf(self, owner: str) -> _FakeFunction:  # noqa: N802
        return _FakeFunction(self._balances.get(owner.lower(), 0))


class _FakeContract:
    def __init__(self, functions: _FakeFunctions) -> None:
        self.functions = functions


@dataclass
class FakeEth:
    balances: dict[str, int] = field(default_factory=dict)
    blocks: dict[int | str, AttributeDict] = field(default_factory=dict)
    transactions: dict[str, AttributeDict] = field(default_factory=dict)
    receipts: dict[str, AttributeDict] = field(default_factory=dict)
    logs: list[AttributeDict] = field(default_factory=list)
    tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    token_balances: dict[str, dict[str, int]] = field(default_factory=dict)
    block_number: int = 20_000_000
    chain_id: int = 1
    gas_price: int = 20 * 10**9
    max_priority_fee: int = 1 * 10**9
    last_log_filter: dict[str, Any] | None = None

    def get_balance(self, address: str) -> int:
        return self.balances.get(address.lower(), 0)

    def get_block(self, ident: int | str, full_transactions: bool = False) -> AttributeDict:
        if ident == "latest":
            ident = self.block_number
        try:
            return self.blocks[ident]
        except KeyError as exc:
            raise ValueError(f"block {ident} not found") from exc

    def get_transaction(self, tx_hash: str) -> AttributeDict:
        try:
            return self.transactions[tx_hash]
        except KeyError as exc:
            raise ValueError("transaction not found") from exc

    def get_transaction_receipt(self, tx_hash: str) -> AttributeDict:
        try:
            return self.receipts[tx_hash]
        except KeyError as exc:
            raise ValueError("receipt not found") from exc

    def get_code(self, address: str) -> HexBytes:
        return HexBytes("0x6080") if address.lower() in self.tokens else HexBytes(b"")

    def get_logs(self, params: dict[str, Any]) -> list[AttributeDict]:
        self.last_log_filter = params
        lo, hi = params["fromBlock"], params["toBlock"]
        return [log for log in self.logs if lo <= log["blockNumber"] <= hi]

    def contract(self, address: str, abi: Any) -> _FakeContract:
        token = self.tokens.get(address.lower())
        if token is None:
            raise ValueError("not a contract")
        return _FakeContract(_FakeFunctions(token, self.token_balances.get(address.lower(), {})))


@dataclass
class FakeEns:
    names: dict[str, str] = field(default_factory=dict)

    def address(self, name: str) -> str | None:
        return self.names.get(name)


@dataclass
class FakeWeb3:
    eth: FakeEth
    ens: FakeEns


@pytest.fixture
def fake_eth() -> FakeEth:
    eth = FakeEth()
    eth.balances[VITALIK.lower()] = 1_234_500_000_000_000_000  # 1.2345 ETH
    latest = eth.block_number
    eth.blocks[latest] = AttributeDict(
        {
            "number": latest,
            "hash": HexBytes("0x" + "11" * 32),
            "parentHash": HexBytes("0x" + "22" * 32),
            "timestamp": 1_700_000_000,
            "miner": HOLDER_A,
            "gasUsed": 15_000_000,
            "gasLimit": 30_000_000,
            "baseFeePerGas": 12 * 10**9,
            "transactions": [HexBytes("0x" + "33" * 32)] * 3,
        }
    )
    eth.transactions[TX_HASH] = AttributeDict(
        {
            "hash": HexBytes(TX_HASH),
            "blockNumber": latest,
            "from": HOLDER_A,
            "to": HOLDER_B,
            "value": 5 * 10**17,
            "nonce": 7,
            "gas": 21_000,
            "gasPrice": 20 * 10**9,
            "input": HexBytes(b""),
        }
    )
    eth.receipts[TX_HASH] = AttributeDict(
        {
            "status": 1,
            "gasUsed": 21_000,
            "effectiveGasPrice": 20 * 10**9,
            "logs": [],
            "contractAddress": None,
        }
    )
    eth.tokens[USDC.lower()] = {
        "name": "USD Coin",
        "symbol": "USDC",
        "decimals": 6,
        "total_supply": 25_000_000_000 * 10**6,
    }
    eth.token_balances[USDC.lower()] = {VITALIK.lower(): 1_500_000}  # 1.5 USDC
    eth.logs = [
        make_transfer_log(
            block=latest, index=0, sender=HOLDER_A, recipient=HOLDER_B, amount=5 * 10**6
        ),
        make_transfer_log(
            block=latest - 1, index=1, sender=HOLDER_B, recipient=HOLDER_A, amount=2_000_000 * 10**6
        ),
        make_transfer_log(
            block=latest - 3000,
            index=0,
            sender=HOLDER_A,
            recipient=HOLDER_B,
            amount=9_000_000 * 10**6,
        ),
    ]
    return eth


@pytest.fixture
def fake_web3(fake_eth: FakeEth) -> FakeWeb3:
    return FakeWeb3(eth=fake_eth, ens=FakeEns(names={"vitalik.eth": VITALIK}))


@pytest.fixture
def settings() -> Settings:
    return Settings(etherscan_api_key="", _env_file=None)  # type: ignore[call-arg]


@pytest.fixture
def rpc(fake_web3: FakeWeb3, settings: Settings) -> RpcClient:
    return RpcClient(fake_web3, max_log_block_range=settings.max_log_block_range)  # type: ignore[arg-type]


@pytest.fixture
def app_state(settings: Settings, rpc: RpcClient) -> AppState:
    return AppState(settings=settings, rpc=rpc, etherscan=None)
