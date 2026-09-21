"""Runtime configuration, loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All knobs the server reads. Field names map to upper-case env vars (ETH_RPC_URL, ...)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Data sources (ADR-0002) ---
    eth_rpc_url: str = "https://ethereum-rpc.publicnode.com"
    """JSON-RPC endpoint used for all state queries."""

    etherscan_api_key: str = ""
    """Optional. Empty string disables the two address-history tools with a clear error."""

    etherscan_base_url: str = "https://api.etherscan.io/v2/api"
    chain_id: int = 1
    """Ethereum mainnet. Etherscan V2 is multi-chain and needs this explicitly."""

    request_timeout_seconds: float = 20.0
    max_log_block_range: int = 2000
    """Hard cap for eth_getLogs scans so free-tier RPC limits are respected."""

    max_history_items: int = 100
    """Hard cap for Etherscan list endpoints regardless of what the caller asks for."""

    # --- HTTP transport (ADR-0003) ---
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    mcp_stateless: bool = True
    """Stateless streamable-http so replicas behind one Service need no sticky sessions."""

    mcp_dns_rebinding_protection: bool = False
    """The SDK can reject requests whose Host header is not localhost. Inside a cluster the
    Host header is the Service name, so this stays off; the network boundary is the
    cluster, not the Host header. Turn on when exposing the port directly on a laptop."""

    log_level: str = "INFO"
