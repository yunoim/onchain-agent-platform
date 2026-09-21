# onchain-agent

FastAPI service that answers natural-language questions about Ethereum by driving the
read-only tools of [`onchain-mcp`](../mcp-server/README.md) through an LLM behind the
LiteLLM gateway. Python 3.12, `openai` SDK (pointed at the gateway, never a provider),
`mcp` SDK 2.x client, managed with `uv`.

## How a question is answered

```
POST /ask {"question": "..."}
  -> tools/list from the MCP server (cached)          streamable-http
  -> chat.completions(messages, tools) via gateway    OpenAI-compatible
  -> for each tool_call: tools/call on the MCP server, append result
  -> repeat until the model answers, at most MAX_TOOL_ITERATIONS times
  -> if the budget runs out: one final call without tools
<- {"answer", "model", "iterations", "budget_exhausted", "tool_calls": [...], "usage", "estimated_cost_usd"}
```

Every round-trip is bounded and recorded, so the response shows its work and `/metrics`
accounts for tokens and cost per model alias.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/ask` | `{"question": str, "model": str?}`; `model` is a gateway alias |
| GET | `/tools` | Tools currently offered to the model |
| GET | `/healthz` | Liveness |
| GET | `/readyz` | 200 only when the MCP server and the gateway both answer |
| GET | `/metrics` | Prometheus: requests, latency, LLM calls, tokens, cost, tool calls, iterations |
| GET | `/docs` | OpenAPI UI |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:4000` | LiteLLM gateway |
| `LLM_API_KEY` (or `LITELLM_MASTER_KEY`) | `sk-local-dev-change-me` | Gateway key |
| `LLM_MODEL` | `local-default` | Alias from `services/gateway/litellm/config.yaml` |
| `MCP_SERVER_URL` | `http://localhost:8000/mcp` | MCP server, streamable-http |
| `MAX_TOOL_ITERATIONS` | `8` | LLM round-trips per question |
| `MAX_TOOL_RESULT_CHARS` | `6000` | Tool output truncation before it reaches the model |
| `MODEL_PRICES_JSON` | Claude aliases | USD per 1M tokens `[prompt, completion]` per alias; unknown alias = 0 |
| `AGENT_HOST` / `AGENT_PORT` | `127.0.0.1` / `8080` | Bind address |

## Run

```powershell
uv sync
```

```powershell
uv run pytest
```

```powershell
uv run onchain-agent
```

The full local stack (MCP server, gateway, agent) is started from the repository root with
`docker compose up --build`; see the top-level README.

## Layout

```
src/onchain_agent/
├── main.py        # FastAPI app factory, routes, uvicorn entry point
├── agent.py       # bounded tool-calling loop, usage/cost accounting, <think> stripping
├── mcp_tools.py   # MCP <-> OpenAI tool format adapter (ToolExecutor seam)
├── metrics.py     # Prometheus counters/histograms
└── config.py      # Settings from env
tests/             # scripted fake chat client + fake tool executor; API tests via TestClient
```
