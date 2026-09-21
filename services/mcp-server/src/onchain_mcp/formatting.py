"""Helpers that turn web3 return values into plain, JSON-serialisable, LLM-friendly data."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

WEI_PER_ETH = 10**18
WEI_PER_GWEI = 10**9


def wei_to_eth(wei: int) -> str:
    """Exact decimal string, no float rounding. 1234500000000000000 -> '1.2345'."""
    return _format_units(wei, 18)


def wei_to_gwei(wei: int) -> str:
    return _format_units(wei, 9)


def format_units(amount: int, decimals: int) -> str:
    """Token amount in human units, exact. format_units(1500000, 6) -> '1.5'."""
    return _format_units(amount, decimals)


def parse_units(amount: str | int | float, decimals: int) -> int:
    """Human units -> raw integer amount. parse_units('1.5', 6) -> 1500000."""
    quantised = Decimal(str(amount)) * (Decimal(10) ** decimals)
    return int(quantised)


def _format_units(amount: int, decimals: int) -> str:
    if decimals == 0:
        return str(amount)
    value = Decimal(amount) / (Decimal(10) ** decimals)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def to_jsonable(value: Any) -> Any:
    """Recursively convert HexBytes / bytes / AttributeDict into str / dict / list."""
    if isinstance(value, bytes | bytearray):
        return "0x" + bytes(value).hex()
    if isinstance(value, Mapping):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(v) for v in value]
    return value
