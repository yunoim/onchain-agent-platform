"""Runtime configuration from environment variables (or a .env file)."""

from __future__ import annotations

import json

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM gateway (ADR-0004): the agent speaks OpenAI-compatible HTTP to LiteLLM only ---
    llm_base_url: str = "http://localhost:4000"
    llm_api_key: str = Field(
        default="sk-local-dev-change-me",
        validation_alias=AliasChoices("LLM_API_KEY", "LITELLM_MASTER_KEY"),
    )
    llm_model: str = "local-default"
    """Model *alias* defined in services/gateway/litellm/config.yaml, never a provider id."""
    llm_timeout_seconds: float = 180.0
    llm_temperature: float = 0.1

    # --- MCP server (ADR-0003: streamable-http) ---
    mcp_server_url: str = "http://localhost:8000/mcp"
    mcp_timeout_seconds: float = 90.0

    # --- Loop bounds: the model cannot burn RPC quota or LLM budget indefinitely ---
    max_tool_iterations: int = 8
    max_tool_result_chars: int = 6000
    """Tool output longer than this is truncated before it goes back to the model."""

    # --- Cost accounting for /metrics. USD per 1M tokens: [prompt, completion] per alias ---
    model_prices_json: str = '{"claude-default": [3.0, 15.0], "claude-fast": [1.0, 5.0]}'

    agent_host: str = "127.0.0.1"
    agent_port: int = 8080
    log_level: str = "INFO"

    def model_prices(self) -> dict[str, tuple[float, float]]:
        raw = json.loads(self.model_prices_json)
        return {k: (float(v[0]), float(v[1])) for k, v in raw.items()}
