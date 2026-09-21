from hexbytes import HexBytes
from web3.datastructures import AttributeDict

from onchain_mcp.formatting import format_units, parse_units, to_jsonable, wei_to_eth, wei_to_gwei


def test_wei_to_eth_is_exact() -> None:
    assert wei_to_eth(1_234_500_000_000_000_000) == "1.2345"
    assert wei_to_eth(0) == "0"
    assert wei_to_eth(1) == "0.000000000000000001"
    assert wei_to_eth(10**18) == "1"


def test_wei_to_gwei() -> None:
    assert wei_to_gwei(20_000_000_000) == "20"
    assert wei_to_gwei(1_500_000_000) == "1.5"


def test_format_and_parse_units_roundtrip() -> None:
    assert format_units(1_500_000, 6) == "1.5"
    assert format_units(42, 0) == "42"
    assert parse_units("1.5", 6) == 1_500_000
    assert parse_units("1000000", 6) == 1_000_000 * 10**6
    assert parse_units(0, 18) == 0


def test_to_jsonable_flattens_web3_types() -> None:
    value = AttributeDict({"hash": HexBytes("0x0102"), "nested": [HexBytes(b"\xff")], "n": 3})
    assert to_jsonable(value) == {"hash": "0x0102", "nested": ["0xff"], "n": 3}
