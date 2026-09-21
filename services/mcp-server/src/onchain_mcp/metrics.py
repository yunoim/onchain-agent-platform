"""Prometheus instrumentation for tool calls. Scraped from /metrics when running over HTTP."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

from prometheus_client import Counter, Histogram

TOOL_CALLS = Counter(
    "onchain_mcp_tool_calls_total",
    "Number of MCP tool invocations",
    labelnames=("tool", "status"),
)
TOOL_DURATION = Histogram(
    "onchain_mcp_tool_duration_seconds",
    "Wall-clock duration of MCP tool invocations",
    labelnames=("tool",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)


def instrumented[F: Callable[..., Any]](fn: F) -> F:
    """Count and time a tool function. Works with sync tools (the SDK threads them)."""

    name = fn.__name__

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        status = "ok"
        try:
            return fn(*args, **kwargs)
        except Exception:
            status = "error"
            raise
        finally:
            TOOL_DURATION.labels(tool=name).observe(time.perf_counter() - started)
            TOOL_CALLS.labels(tool=name, status=status).inc()

    return wrapper  # type: ignore[return-value]
