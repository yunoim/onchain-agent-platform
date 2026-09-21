import pytest
from mcp.server.mcpserver.exceptions import ToolError
from web3 import Web3

from onchain_mcp.clients.rpc import TRANSFER_TOPIC, RpcClient
from tests.conftest import HOLDER_A, HOLDER_B, TX_HASH, USDC, VITALIK, FakeEth


def test_transfer_topic_matches_keccak() -> None:
    assert Web3.to_hex(Web3.keccak(text="Transfer(address,address,uint256)")) == TRANSFER_TOPIC


class TestResolveAddress:
    def test_hex_is_checksummed(self, rpc: RpcClient) -> None:
        assert rpc.resolve_address(VITALIK.lower()) == VITALIK

    def test_ens_name_resolves(self, rpc: RpcClient) -> None:
        assert rpc.resolve_address("vitalik.eth") == VITALIK

    def test_unknown_ens_name_raises_tool_error(self, rpc: RpcClient) -> None:
        with pytest.raises(ToolError, match="does not resolve"):
            rpc.resolve_address("nobody-owns-this-name.eth")

    def test_garbage_raises_tool_error(self, rpc: RpcClient) -> None:
        with pytest.raises(ToolError, match="neither a valid hex address"):
            rpc.resolve_address("hello world")


class TestStateQueries:
    def test_balance(self, rpc: RpcClient) -> None:
        assert rpc.get_balance_wei(VITALIK) == 1_234_500_000_000_000_000

    def test_block_by_tag_and_number(self, rpc: RpcClient, fake_eth: FakeEth) -> None:
        latest = rpc.get_block("latest")
        assert latest["number"] == fake_eth.block_number
        assert latest["transaction_count"] == 3
        assert latest["hash"].startswith("0x")
        by_number = rpc.get_block(str(fake_eth.block_number))
        assert by_number == latest
        by_hex = rpc.get_block(hex(fake_eth.block_number))
        assert by_hex == latest

    def test_bad_block_identifier(self, rpc: RpcClient) -> None:
        with pytest.raises(ToolError, match="not a block number"):
            rpc.get_block("yesterday")

    def test_rpc_failure_becomes_tool_error(self, rpc: RpcClient) -> None:
        with pytest.raises(ToolError, match="RPC request failed"):
            rpc.get_block(1)  # not present in the fake

    def test_transaction_with_receipt(self, rpc: RpcClient) -> None:
        tx, receipt = rpc.get_transaction(TX_HASH)
        assert tx["from"] == HOLDER_A
        assert receipt is not None
        assert receipt["status"] == 1

    def test_pending_transaction_has_no_receipt(self, rpc: RpcClient, fake_eth: FakeEth) -> None:
        del fake_eth.receipts[TX_HASH]
        _, receipt = rpc.get_transaction(TX_HASH)
        assert receipt is None

    def test_gas_snapshot(self, rpc: RpcClient) -> None:
        snap = rpc.gas_snapshot()
        assert snap["gas_price_wei"] == 20 * 10**9
        assert snap["base_fee_per_gas_wei"] == 12 * 10**9
        assert snap["max_priority_fee_per_gas_wei"] == 1 * 10**9


class TestErc20:
    def test_metadata(self, rpc: RpcClient) -> None:
        meta = rpc.erc20_metadata(USDC)
        assert meta["symbol"] == "USDC"
        assert meta["decimals"] == 6

    def test_metadata_rejects_non_contract(self, rpc: RpcClient) -> None:
        with pytest.raises(ToolError, match="no contract code"):
            rpc.erc20_metadata(HOLDER_A)

    def test_balance(self, rpc: RpcClient) -> None:
        assert rpc.erc20_balance_raw(USDC, VITALIK) == 1_500_000
        assert rpc.erc20_balance_raw(USDC, HOLDER_B) == 0

    def test_transfer_logs_decode_and_clamp(self, rpc: RpcClient, fake_eth: FakeEth) -> None:
        latest = fake_eth.block_number
        logs = rpc.transfer_logs(USDC, latest - 10_000, latest)
        # range clamped to max_log_block_range (2000) -> the 3000-blocks-old log is excluded
        assert fake_eth.last_log_filter is not None
        assert fake_eth.last_log_filter["fromBlock"] == latest - 2000 + 1
        assert fake_eth.last_log_filter["topics"] == [TRANSFER_TOPIC]
        assert len(logs) == 2
        big = max(logs, key=lambda log: log.raw_amount)
        assert big.from_address == HOLDER_B
        assert big.to_address == HOLDER_A
        assert big.raw_amount == 2_000_000 * 10**6
