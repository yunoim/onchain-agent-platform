"""Etherscan API V2 client for address history (the optional second data tier, ADR-0002)."""

from __future__ import annotations

from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

MISSING_KEY_MESSAGE = (
    "Address history tools need an Etherscan API key. Set ETHERSCAN_API_KEY "
    "(free tier at https://etherscan.io/apis). State tools such as get_eth_balance, "
    "get_block and get_recent_token_transfers work without it."
)


class EtherscanClient:
    """Minimal wrapper around the `account` module of Etherscan V2."""

    def __init__(
        self,
        api_key: str,
        *,
        chain_id: int = 1,
        base_url: str = "https://api.etherscan.io/v2/api",
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("EtherscanClient requires a non-empty api_key")
        self._api_key = api_key
        self._chain_id = chain_id
        self._http = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._http.close()

    def address_transactions(self, address: str, *, limit: int) -> list[dict[str, Any]]:
        rows = self._account("txlist", address=address, offset=limit)
        return [_normalise_tx(r) for r in rows]

    def address_token_transfers(
        self, address: str, *, limit: int, contract_address: str | None = None
    ) -> list[dict[str, Any]]:
        extra = {"contractaddress": contract_address} if contract_address else {}
        rows = self._account("tokentx", address=address, offset=limit, **extra)
        return [_normalise_token_tx(r) for r in rows]

    # ---- internals -------------------------------------------------------------------

    def _account(
        self, action: str, *, address: str, offset: int, **extra: str
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "chainid": self._chain_id,
            "module": "account",
            "action": action,
            "address": address,
            "startblock": 0,
            "endblock": 99_999_999,
            "page": 1,
            "offset": offset,
            "sort": "desc",
            "apikey": self._api_key,
            **extra,
        }
        try:
            response = self._http.get("", params=params)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as exc:
            raise ToolError(f"Etherscan request failed: {type(exc).__name__}: {exc}") from exc
        except ValueError as exc:
            raise ToolError("Etherscan returned a non-JSON response") from exc

        result = body.get("result")
        status = str(body.get("status", ""))
        if status == "1" and isinstance(result, list):
            return result
        # status "0" covers both "No transactions found" (result == []) and real errors
        # (result is a string such as "Invalid API Key").
        if isinstance(result, list):
            return result
        message = body.get("message", "unknown error")
        detail = result if isinstance(result, str) else ""
        raise ToolError(f"Etherscan error: {message}. {detail}".strip())


def _normalise_tx(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "hash": row.get("hash"),
        "block_number": _int(row.get("blockNumber")),
        "timestamp": _int(row.get("timeStamp")),
        "from": row.get("from"),
        "to": row.get("to") or None,
        "value_wei": _int(row.get("value")),
        "gas_used": _int(row.get("gasUsed")),
        "gas_price_wei": _int(row.get("gasPrice")),
        "is_error": row.get("isError") == "1",
        "method_id": _opt_hex(row.get("methodId")),
        "function_name": row.get("functionName") or None,
        "contract_created": row.get("contractAddress") or None,
    }


def _normalise_token_tx(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "hash": row.get("hash"),
        "block_number": _int(row.get("blockNumber")),
        "timestamp": _int(row.get("timeStamp")),
        "from": row.get("from"),
        "to": row.get("to"),
        "contract_address": row.get("contractAddress"),
        "token_name": row.get("tokenName"),
        "token_symbol": row.get("tokenSymbol"),
        "token_decimals": _int(row.get("tokenDecimal")),
        "value_raw": _int(row.get("value")),
    }


def _opt_hex(value: Any) -> str | None:
    """Etherscan sends "0x" for plain transfers; treat that as absent."""
    return value if isinstance(value, str) and len(value) > 2 else None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
