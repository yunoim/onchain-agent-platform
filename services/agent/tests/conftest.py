"""Fakes for the two seams the agent depends on: the chat client and the tool executor."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from openai.types.chat import ChatCompletion

from onchain_agent.config import Settings
from onchain_agent.mcp_tools import ToolResult, ToolSpec

BALANCE_SPEC = ToolSpec(
    name="get_eth_balance",
    description="Get the native ETH balance of an address or ENS name.",
    input_schema={"type": "object", "properties": {"address": {"type": "string"}}},
)
GAS_SPEC = ToolSpec(
    name="get_gas_price", description="Get gas prices.", input_schema={"type": "object"}
)


def completion(
    *,
    content: str | None = None,
    tool_calls: list[tuple[str, str, dict[str, Any] | str]] | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
) -> ChatCompletion:
    """Build a ChatCompletion the way the gateway would return it.

    tool_calls: list of (id, name, arguments) where arguments is a dict or a raw string.
    """
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": args if isinstance(args, str) else json.dumps(args),
                },
            }
            for call_id, name, args in tool_calls
        ]
    return ChatCompletion.model_validate(
        {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": "local-default",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                    "message": message,
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
    )


@dataclass
class FakeChat:
    """Returns scripted completions in order and records every request it received."""

    script: list[ChatCompletion]
    requests: list[dict[str, Any]] = field(default_factory=list)

    async def complete(
        self, *, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> ChatCompletion:
        self.requests.append({"model": model, "messages": list(messages), "tools": tools})
        if not self.script:
            raise AssertionError("FakeChat script exhausted")
        return self.script.pop(0)


@dataclass
class FakeTools:
    results: dict[str, ToolResult] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    raise_on: set[str] = field(default_factory=set)

    async def list_tools(self) -> list[ToolSpec]:
        return [BALANCE_SPEC, GAS_SPEC]

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append((name, arguments))
        if name in self.raise_on:
            raise ConnectionError("mcp down")
        return self.results.get(name, ToolResult(text=f"unknown tool {name}", is_error=True))


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, max_tool_iterations=3, max_tool_result_chars=50)  # type: ignore[call-arg]


@pytest.fixture
def fake_tools() -> FakeTools:
    return FakeTools(
        results={
            "get_eth_balance": ToolResult(
                text=json.dumps(
                    {
                        "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
                        "balance_eth": "6.7126",
                    }
                )
            ),
            "get_gas_price": ToolResult(text=json.dumps({"gas_price_gwei": "0.72"})),
        }
    )
