import json

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from onchain_mcp.clients.etherscan import EtherscanClient
from tests.conftest import HOLDER_A, HOLDER_B, VITALIK

TX_ROW = {
    "blockNumber": "19999999",
    "timeStamp": "1700000000",
    "hash": "0x" + "cd" * 32,
    "from": VITALIK.lower(),
    "to": HOLDER_A.lower(),
    "value": "1000000000000000000",
    "gasUsed": "21000",
    "gasPrice": "20000000000",
    "isError": "0",
    "methodId": "0x",
    "functionName": "",
    "contractAddress": "",
}

TOKEN_ROW = {
    "blockNumber": "19999998",
    "timeStamp": "1699999000",
    "hash": "0x" + "ef" * 32,
    "from": HOLDER_B.lower(),
    "to": VITALIK.lower(),
    "contractAddress": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "tokenName": "USD Coin",
    "tokenSymbol": "USDC",
    "tokenDecimal": "6",
    "value": "2500000",
}


def _client(handler) -> EtherscanClient:
    return EtherscanClient("test-key", transport=httpx.MockTransport(handler))


def test_requires_api_key() -> None:
    with pytest.raises(ValueError):
        EtherscanClient("")


def test_address_transactions_sends_v2_params_and_normalises() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"status": "1", "message": "OK", "result": [TX_ROW]})

    rows = _client(handler).address_transactions(VITALIK, limit=5)
    assert seen["chainid"] == "1"
    assert seen["module"] == "account"
    assert seen["action"] == "txlist"
    assert seen["offset"] == "5"
    assert seen["sort"] == "desc"
    assert seen["apikey"] == "test-key"
    assert rows == [
        {
            "hash": TX_ROW["hash"],
            "block_number": 19_999_999,
            "timestamp": 1_700_000_000,
            "from": VITALIK.lower(),
            "to": HOLDER_A.lower(),
            "value_wei": 10**18,
            "gas_used": 21_000,
            "gas_price_wei": 20 * 10**9,
            "is_error": False,
            "method_id": None,
            "function_name": None,
            "contract_created": None,
        }
    ]


def test_token_transfers_with_contract_filter() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"status": "1", "message": "OK", "result": [TOKEN_ROW]})

    rows = _client(handler).address_token_transfers(
        VITALIK, limit=3, contract_address=TOKEN_ROW["contractAddress"]
    )
    assert seen["action"] == "tokentx"
    assert seen["contractaddress"] == TOKEN_ROW["contractAddress"]
    assert rows[0]["token_symbol"] == "USDC"
    assert rows[0]["token_decimals"] == 6
    assert rows[0]["value_raw"] == 2_500_000


def test_empty_result_is_not_an_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "0", "message": "No transactions found", "result": []}
        )

    assert _client(handler).address_transactions(VITALIK, limit=5) == []


def test_api_error_string_becomes_tool_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "0", "message": "NOTOK", "result": "Invalid API Key"}
        )

    with pytest.raises(ToolError, match="Invalid API Key"):
        _client(handler).address_transactions(VITALIK, limit=5)


def test_http_failure_becomes_tool_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream down")

    with pytest.raises(ToolError, match="Etherscan request failed"):
        _client(handler).address_transactions(VITALIK, limit=5)


def test_non_json_becomes_tool_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>rate limited</html>")

    with pytest.raises(ToolError, match="non-JSON"):
        _client(handler).address_transactions(VITALIK, limit=5)


def test_bodies_are_json_serialisable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "1", "message": "OK", "result": [TX_ROW]})

    json.dumps(_client(handler).address_transactions(VITALIK, limit=1))
