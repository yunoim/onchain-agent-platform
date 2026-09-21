"""FastAPI application: POST /ask plus health, readiness, tool listing and metrics."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import openai
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from onchain_agent import __version__, metrics
from onchain_agent.agent import Agent, OpenAIChatClient
from onchain_agent.config import Settings
from onchain_agent.mcp_tools import McpToolbox

log = logging.getLogger("onchain-agent")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    model: str | None = Field(default=None, description="Gateway alias; defaults to LLM_MODEL")


def create_app(settings: Settings | None = None, agent: Agent | None = None) -> FastAPI:
    """Build the app. Tests pass a pre-built `agent` with fakes; production builds one."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        if agent is not None:
            app.state.agent = agent
        else:
            toolbox = McpToolbox(settings.mcp_server_url, settings.mcp_timeout_seconds)
            llm = OpenAIChatClient(
                settings.llm_base_url,
                settings.llm_api_key,
                settings.llm_timeout_seconds,
                settings.llm_temperature,
            )
            app.state.agent = Agent(llm, toolbox, settings)
        yield

    app = FastAPI(
        title="onchain-agent",
        version=__version__,
        description="Answers questions about Ethereum by driving read-only MCP tools "
        "through an LLM gateway.",
        lifespan=lifespan,
    )

    @app.post("/ask")
    async def ask(body: AskRequest, request: Request) -> dict[str, Any]:
        started = time.perf_counter()
        status = "ok"
        try:
            result = await request.app.state.agent.run(body.question, body.model)
            return result.to_dict()
        except openai.APIStatusError as exc:
            status = "gateway_error"
            raise HTTPException(
                status_code=502, detail=f"LLM gateway returned {exc.status_code}: {exc.message}"
            ) from exc
        except openai.APIConnectionError as exc:
            status = "gateway_unreachable"
            raise HTTPException(status_code=503, detail=f"LLM gateway unreachable: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - keep the boundary; the log has the trace
            status = "error"
            log.exception("ask failed")
            raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
        finally:
            metrics.REQUESTS.labels(status=status).inc()
            metrics.REQUEST_DURATION.observe(time.perf_counter() - started)

    @app.get("/tools")
    async def tools(request: Request) -> list[dict[str, Any]]:
        specs = await request.app.state.agent._tools.list_tools()  # noqa: SLF001
        return [{"name": s.name, "description": s.description} for s in specs]

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "onchain-agent", "version": __version__}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(request: Request) -> JSONResponse:
        """Ready only when both upstreams answer: MCP tool list and gateway liveliness."""
        s: Settings = request.app.state.settings
        checks: dict[str, str] = {}
        try:
            await request.app.state.agent._tools.list_tools()  # noqa: SLF001
            checks["mcp"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["mcp"] = f"error: {type(exc).__name__}"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{s.llm_base_url.rstrip('/')}/health/liveliness")
            checks["gateway"] = "ok" if r.status_code == 200 else f"http {r.status_code}"
        except Exception as exc:  # noqa: BLE001
            checks["gateway"] = f"error: {type(exc).__name__}"
        ready = all(v == "ok" for v in checks.values())
        return JSONResponse({"ready": ready, "checks": checks}, status_code=200 if ready else 503)

    @app.get("/metrics", include_in_schema=False)
    async def prometheus() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


def main() -> None:
    import uvicorn

    settings = Settings()
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(
        create_app(settings),
        host=settings.agent_host,
        port=settings.agent_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
