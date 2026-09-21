"""Adapter between MCP tools and the OpenAI tool-calling format.

`ToolExecutor` is the seam the agent depends on; `McpToolbox` is the real implementation
that talks streamable-http to the MCP server. Tests substitute a fake executor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from mcp.client import Client


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    text: str
    is_error: bool = False


class ToolExecutor(Protocol):
    async def list_tools(self) -> list[ToolSpec]: ...

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult: ...


@dataclass
class McpToolbox:
    """Talks to one MCP server over streamable-http. A fresh session per call keeps the
    agent stateless, which is what a stateless MCP server behind a Service expects."""

    url: str
    timeout_seconds: float = 90.0
    _cache: list[ToolSpec] = field(default_factory=list, repr=False)

    async def list_tools(self, *, refresh: bool = False) -> list[ToolSpec]:
        if self._cache and not refresh:
            return self._cache
        async with Client(self.url, read_timeout_seconds=self.timeout_seconds) as client:
            listed = await client.list_tools()
        self._cache = [
            ToolSpec(
                name=t.name,
                description=t.description or "",
                input_schema=dict(t.input_schema or {"type": "object", "properties": {}}),
            )
            for t in listed.tools
        ]
        return self._cache

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        async with Client(self.url, read_timeout_seconds=self.timeout_seconds) as client:
            result = await client.call_tool(name, arguments)
        text = "\n".join(getattr(part, "text", "") for part in result.content).strip()
        return ToolResult(text=text or "(no content)", is_error=bool(result.is_error))


def to_openai_tools(specs: list[ToolSpec]) -> list[dict[str, Any]]:
    """MCP tool -> OpenAI `tools=[...]` entry. Schemas are already JSON Schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.input_schema,
            },
        }
        for spec in specs
    ]
