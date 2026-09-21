"""The tool-calling loop.

    question -> [LLM with tool schemas] -> tool_calls? -> run via MCP -> feed back -> ...
                                        -> no tool_calls -> final answer

Bounded by `max_tool_iterations`; when the budget is exhausted the model is asked once more,
without tools, to answer from what it has. Every LLM round-trip and tool call is recorded
so the API response can show its work and /metrics can account for tokens and cost.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from onchain_agent import metrics
from onchain_agent.config import Settings
from onchain_agent.mcp_tools import ToolExecutor, ToolResult, to_openai_tools

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an on-chain analyst with read-only access to Ethereum mainnet through tools.
Rules:
- Always answer from tool results. Never invent addresses, balances, hashes or block numbers.
- Amounts in tool results are exact decimal strings; quote them as given (round only for
  readability and say so). Mention the block number a reading was taken at.
- Addresses may be ENS names; pass them to tools as-is.
- If a tool reports that an API key is missing, say which capability is unavailable and
  answer with the other tools instead of retrying the same call.
- Prefer few, well-chosen tool calls. Stop calling tools once you can answer.
- Be concise: a short summary first, then the key numbers.
"""

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: Any) -> None:
        if other is None:
            return
        self.prompt_tokens += int(getattr(other, "prompt_tokens", 0) or 0)
        self.completion_tokens += int(getattr(other, "completion_tokens", 0) or 0)
        self.total_tokens += int(getattr(other, "total_tokens", 0) or 0)


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    is_error: bool
    duration_ms: int
    result_preview: str


@dataclass
class AgentResult:
    answer: str
    model: str
    iterations: int
    budget_exhausted: bool
    usage: Usage
    estimated_cost_usd: float
    tool_calls: list[ToolCallRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChatClient(Protocol):
    async def complete(
        self, *, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> ChatCompletion: ...


class OpenAIChatClient:
    """Real client. Points the OpenAI SDK at the LiteLLM gateway; never at a provider."""

    def __init__(self, base_url: str, api_key: str, timeout: float, temperature: float) -> None:
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._temperature = temperature

    async def complete(
        self, *, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> ChatCompletion:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self._temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return await self._client.chat.completions.create(**kwargs)


class Agent:
    def __init__(self, llm: ChatClient, tools: ToolExecutor, settings: Settings) -> None:
        self._llm = llm
        self._tools = tools
        self._settings = settings
        self._prices = settings.model_prices()

    async def run(self, question: str, model: str | None = None) -> AgentResult:
        model = model or self._settings.llm_model
        specs = await self._tools.list_tools()
        openai_tools = to_openai_tools(specs)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        usage = Usage()
        records: list[ToolCallRecord] = []
        iterations = 0

        for iterations in range(1, self._settings.max_tool_iterations + 1):
            response = await self._complete(model, messages, openai_tools, usage)
            message = response.choices[0].message
            tool_calls = list(message.tool_calls or [])
            if not tool_calls:
                return self._finish(
                    clean_answer(message.content), model, iterations, False, usage, records
                )

            messages.append(_assistant_message(message.content, tool_calls))
            for call in tool_calls:
                record, tool_message = await self._execute(call)
                records.append(record)
                messages.append(tool_message)

        # Budget exhausted: one last round without tools so the user still gets an answer.
        messages.append(
            {
                "role": "user",
                "content": "Tool budget exhausted. Answer now using only the information "
                "gathered so far, and say what could not be verified.",
            }
        )
        response = await self._complete(model, messages, None, usage)
        answer = clean_answer(response.choices[0].message.content)
        return self._finish(answer, model, iterations + 1, True, usage, records)

    # ---- internals -------------------------------------------------------------------

    async def _complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        usage: Usage,
    ) -> ChatCompletion:
        try:
            response = await self._llm.complete(model=model, messages=messages, tools=tools)
        except Exception:
            metrics.LLM_CALLS.labels(model=model, status="error").inc()
            raise
        metrics.LLM_CALLS.labels(model=model, status="ok").inc()
        usage.add(response.usage)
        if response.usage is not None:
            p = int(response.usage.prompt_tokens or 0)
            c = int(response.usage.completion_tokens or 0)
            metrics.LLM_TOKENS.labels(model=model, kind="prompt").inc(p)
            metrics.LLM_TOKENS.labels(model=model, kind="completion").inc(c)
            metrics.LLM_COST_USD.labels(model=model).inc(self._cost(model, p, c))
        return response

    async def _execute(self, call: Any) -> tuple[ToolCallRecord, dict[str, Any]]:
        function = getattr(call, "function", None)
        name = getattr(function, "name", None) or "unknown"
        raw_args = getattr(function, "arguments", "") or "{}"
        started = time.perf_counter()

        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            arguments = {}
            result = ToolResult(
                text=f"Invalid tool arguments ({exc}). Send a JSON object.", is_error=True
            )
        else:
            try:
                result = await self._tools.call(name, arguments)
            except Exception as exc:  # noqa: BLE001 - surfaced to the model, not swallowed
                log.warning("tool %s failed: %s", name, exc)
                result = ToolResult(
                    text=f"Tool call failed: {type(exc).__name__}: {exc}", is_error=True
                )

        duration_ms = int((time.perf_counter() - started) * 1000)
        metrics.TOOL_CALLS.labels(tool=name, status="error" if result.is_error else "ok").inc()
        text = _truncate(result.text, self._settings.max_tool_result_chars)
        record = ToolCallRecord(
            name=name,
            arguments=arguments,
            is_error=result.is_error,
            duration_ms=duration_ms,
            result_preview=_truncate(result.text, 300),
        )
        tool_message = {"role": "tool", "tool_call_id": getattr(call, "id", name), "content": text}
        return record, tool_message

    def _finish(
        self,
        answer: str,
        model: str,
        iterations: int,
        exhausted: bool,
        usage: Usage,
        records: list[ToolCallRecord],
    ) -> AgentResult:
        metrics.TOOL_ITERATIONS.observe(iterations)
        return AgentResult(
            answer=answer,
            model=model,
            iterations=iterations,
            budget_exhausted=exhausted,
            usage=usage,
            estimated_cost_usd=self._cost(model, usage.prompt_tokens, usage.completion_tokens),
            tool_calls=records,
        )

    def _cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        prices = self._prices.get(model)
        if prices is None:
            return 0.0
        return round((prompt_tokens * prices[0] + completion_tokens * prices[1]) / 1_000_000, 6)


def clean_answer(content: str | None) -> str:
    """Drop reasoning blocks some local models emit (qwen3 `<think>`), trim whitespace."""
    if not content:
        return ""
    return THINK_RE.sub("", content).strip()


def _assistant_message(content: str | None, tool_calls: list[Any]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": clean_answer(content) or None,
        "tool_calls": [
            {
                "id": getattr(call, "id", ""),
                "type": "function",
                "function": {
                    "name": getattr(getattr(call, "function", None), "name", ""),
                    "arguments": getattr(getattr(call, "function", None), "arguments", "") or "{}",
                },
            }
            for call in tool_calls
        ],
    }


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"
