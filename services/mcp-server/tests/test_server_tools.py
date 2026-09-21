"""End-to-end tests through the MCP protocol using the SDK's in-memory client.

The server is built with a state factory that injects the fake Web3 / a mocked Etherscan,
so these exercise argument validation, tool dispatch, and error rendering exactly as an
LLM client would see them.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from mcp.client import Client

from onchain_mcp.clients.etherscan import EtherscanClient
from onchain_mcp.clients.rpc import RpcClient
from onchain_mcp.config import Settings
from onchain_mcp.server import build_server
from onchain_mcp.state import AppState
from tests.conftest import HOLDER_A, HOLDER_B, TX_HASH, USDC, VITALIK, FakeWeb3

EXPECTED_TOOLS = {
    "get_eth_balance",
    "get_erc20_balance",
    "get_block",
    "get_gas_price",
    "get_transaction",
    "get_erc20_token_info",
    "get_recent_token_transfers",
    "get_address_transactions",
    "get_address_token_transfers",
}


def _etherscan_stub(rows: list[dict[str, Any]]) -> EtherscanClient:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "1", "message": "OK", "result": rows})

    return EtherscanClient("k", transport=httpx.MockTransport(handler))


@pytest.fixture
def client_factory(fake_web3: FakeWeb3, settings: Settings):
    """Build an in-memory MCP client; pass `etherscan=` to enable the history tier."""

    def make(etherscan: EtherscanClient | None = None) -> Client:
        def factory(s: Settings) -> AppState:
            rpc = RpcClient(fake_web3, max_log_block_range=s.max_log_block_range)  # type: ignore[arg-type]
            return AppState(settings=s, rpc=rpc, etherscan=etherscan)

        return Client(build_server(settings, state_factory=factory))

    return make


async def _call(client: Client, name: str, **args: Any) -> dict[str, Any]:
    result = await client.call_tool(name, args)
    text = result.content[0].text  # type: ignore[union-attr]
    if result.is_error:
        return {"__error__": text}
    return json.loads(text)


async def test_lists_exactly_the_nine_tools(client_factory) -> None:
    async with client_factory() as client:
        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} == EXPECTED_TOOLS
        for tool in tools:
            assert tool.description, f"{tool.name} has no description"
            assert "ctx" not in tool.input_schema.get("properties", {}), (
                "Context leaked into schema"
            )


async def test_get_eth_balance_with_ens(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(client, "get_eth_balance", address="vitalik.eth")
        assert out["address"] == VITALIK
        assert out["balance_eth"] == "1.2345"
        assert out["balance_wei"] == 1_234_500_000_000_000_000


async def test_get_eth_balance_bad_input_is_tool_error(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(client, "get_eth_balance", address="not-an-address")
        assert "neither a valid hex address" in out["__error__"]


async def test_get_erc20_balance(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(client, "get_erc20_balance", contract_address=USDC, address="vitalik.eth")
        assert out["balance"] == "1.5"
        assert out["decimals"] == 6


async def test_get_block_default_latest(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(client, "get_block")
        assert out["transaction_count"] == 3
        assert out["base_fee_per_gas_gwei"] == "12"


async def test_get_gas_price(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(client, "get_gas_price")
        assert out["gas_price_gwei"] == "20"
        assert out["max_priority_fee_per_gas_gwei"] == "1"
        assert out["simple_transfer_cost_eth"] == "0.00042"


async def test_get_transaction(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(client, "get_transaction", tx_hash=TX_HASH)
        assert out["status"] == "success"
        assert out["from"] == HOLDER_A
        assert out["to"] == HOLDER_B
        assert out["value_eth"] == "0.5"
        assert out["fee_paid_eth"] == "0.00042"


async def test_get_erc20_token_info(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(client, "get_erc20_token_info", contract_address=USDC)
        assert out["symbol"] == "USDC"
        assert out["total_supply"] == "25000000000"


async def test_recent_transfers_filters_and_sorts(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(
            client,
            "get_recent_token_transfers",
            contract_address=USDC,
            blocks=500,
            min_amount="1000000",
        )
        assert out["blocks_scanned"] == 500
        assert out["total_transfers_in_range"] == 2
        assert out["matching_transfers"] == 1
        assert out["transfers"][0]["amount"] == "2000000"
        assert out["transfers"][0]["from"] == HOLDER_B


async def test_recent_transfers_caps_block_range(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(
            client, "get_recent_token_transfers", contract_address=USDC, blocks=999_999
        )
        assert out["blocks_scanned"] == 2000


async def test_recent_transfers_rejects_bad_min_amount(client_factory) -> None:
    async with client_factory() as client:
        out = await _call(
            client, "get_recent_token_transfers", contract_address=USDC, min_amount="lots"
        )
        assert "not a number" in out["__error__"]


async def test_history_tools_explain_missing_key(client_factory) -> None:
    async with client_factory() as client:
        for name in ("get_address_transactions", "get_address_token_transfers"):
            out = await _call(client, name, address=VITALIK)
            assert "ETHERSCAN_API_KEY" in out["__error__"], name


async def test_history_tools_with_key(client_factory) -> None:
    rows = [
        {
            "blockNumber": "1",
            "timeStamp": "2",
            "hash": "0x" + "aa" * 32,
            "from": VITALIK.lower(),
            "to": HOLDER_A.lower(),
            "value": "1000000000000000000",
            "gasUsed": "21000",
            "gasPrice": "1",
            "isError": "0",
        }
    ]
    async with client_factory(etherscan=_etherscan_stub(rows)) as client:
        out = await _call(client, "get_address_transactions", address="vitalik.eth", limit=500)
        assert out["count"] == 1
        assert out["transactions"][0]["value_eth"] == "1"
        assert out["transactions"][0]["direction"] == "out"


async def test_history_limit_is_clamped(client_factory) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"status": "1", "message": "OK", "result": []})

    stub = EtherscanClient("k", transport=httpx.MockTransport(handler))
    async with client_factory(etherscan=stub) as client:
        await _call(client, "get_address_token_transfers", address=VITALIK, limit=10_000)
    assert seen["offset"] == "100"
