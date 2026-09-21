"""Prometheus metrics. The agent is where token usage and cost become observable
(ADR-0004: the gateway's own Prometheus export is not relied upon)."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUESTS = Counter("onchain_agent_requests_total", "Questions answered", labelnames=("status",))
REQUEST_DURATION = Histogram(
    "onchain_agent_request_duration_seconds",
    "End-to-end latency of one /ask request",
    buckets=(0.5, 1, 2, 5, 10, 20, 40, 80, 160),
)
LLM_CALLS = Counter(
    "onchain_agent_llm_calls_total", "Chat completion calls", labelnames=("model", "status")
)
LLM_TOKENS = Counter(
    "onchain_agent_llm_tokens_total",
    "Tokens reported by the gateway",
    labelnames=("model", "kind"),  # kind: prompt | completion
)
LLM_COST_USD = Counter(
    "onchain_agent_llm_cost_usd_total",
    "Estimated spend from the price table",
    labelnames=("model",),
)
TOOL_CALLS = Counter(
    "onchain_agent_tool_calls_total", "MCP tool invocations", labelnames=("tool", "status")
)
TOOL_ITERATIONS = Histogram(
    "onchain_agent_tool_iterations",
    "LLM round-trips needed per question",
    buckets=(1, 2, 3, 4, 5, 6, 8, 10),
)
