# onchain-mcp

Read-only Ethereum tools for AI agents, served over the Model Context Protocol (MCP).
Python 3.12, `mcp` SDK 2.x (`MCPServer`), web3.py 8, managed with `uv`.

Nothing in this package can sign, hold keys, or send transactions
([ADR-0001](../../docs/adr/0001-read-only-onchain-access.md)); the test suite and
`scripts/check-no-signing.sh` fail if such code is ever added.

## Tools

| Tool | Source | What it answers |
|---|---|---|
| `get_eth_balance(address)` | RPC | ETH balance of an address or ENS name |
| `get_erc20_balance(contract_address, address)` | RPC | Token balance, decimals applied |
| `get_block(block="latest")` | RPC | Block summary by number, hex, or tag |
| `get_gas_price()` | RPC | Gas price, base fee, priority fee, cost of a simple transfer |
| `get_transaction(tx_hash)` | RPC | Transaction + receipt status |
| `get_erc20_token_info(contract_address)` | RPC | name / symbol / decimals / total supply |
| `get_recent_token_transfers(contract_address, blocks, min_amount, limit)` | RPC logs | Large transfers in the last N blocks (N capped at 2000) |
| `get_address_transactions(address, limit)` | Etherscan V2 | Recent transactions of an address |
| `get_address_token_transfers(address, limit, contract_address?)` | Etherscan V2 | Recent token transfers of an address |

The two Etherscan tools need `ETHERSCAN_API_KEY` (free tier). Without it they return a
message telling the agent which key is missing; everything else keeps working.

## Configuration

Environment variables (or a `.env` file in the working directory). See the repository
[`.env.example`](../../.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `ETH_RPC_URL` | `https://ethereum-rpc.publicnode.com` | JSON-RPC endpoint |
| `ETHERSCAN_API_KEY` | empty | Enables address-history tools |
| `MAX_LOG_BLOCK_RANGE` | `2000` | Cap for `eth_getLogs` scans |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | HTTP bind address |
| `MCP_STATELESS` | `true` | Stateless streamable-http (safe behind a load balancer) |
| `MCP_DNS_REBINDING_PROTECTION` | `false` | Reject non-localhost `Host` headers; keep off inside a cluster |
| `LOG_LEVEL` | `INFO` | Logs go to stderr (stdout is the stdio protocol channel) |

## Run

Install and test:

```powershell
uv sync
```

```powershell
uv run pytest
```

stdio (what Claude Desktop uses):

```powershell
uv run onchain-mcp
```

streamable-http (what the agent and Kubernetes use):

```powershell
uv run onchain-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

Then `GET /healthz` returns `{"status":"ok"}`, `GET /metrics` exposes Prometheus counters
(`onchain_mcp_tool_calls_total`, `onchain_mcp_tool_duration_seconds`), and the MCP
endpoint is `POST /mcp`.

Docker:

```powershell
docker build -t onchain-mcp-server:dev .
```

```powershell
docker run --rm -p 8000:8000 --env-file ..\..\.env onchain-mcp-server:dev
```

## Connect Claude Desktop

Claude Desktop rewrites its config file from memory when it exits, so edit the file only
while the app is fully closed (tray icon, Quit). Then either run the helper, which refuses
to run while Claude is open:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register-claude-desktop.ps1
```

or add the block below to `claude_desktop_config.json` by hand (see
[`claude_desktop_config.example.json`](claude_desktop_config.example.json)). The file lives
at `%APPDATA%\Claude\` for the classic installer, or at
`%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\` for the Microsoft Store
build, whose `%APPDATA%` is virtualised. Start Claude Desktop and ask: *"What is the ETH
balance of vitalik.eth?"* Server logs land next to the config under `...\Local\Claude\logs\`.

```json
{
  "mcpServers": {
    "onchain": {
      "command": "uv",
      "args": ["--directory", "C:\\path\\to\\onchain-agent-platform\\services\\mcp-server", "run", "onchain-mcp"],
      "env": { "ETHERSCAN_API_KEY": "" }
    }
  }
}
```

## Layout

```
src/onchain_mcp/
├── server.py          # MCPServer assembly, lifespan, /healthz, /metrics, CLI
├── config.py          # Settings from env
├── state.py           # AppState (clients) handed to tools via the lifespan context
├── clients/rpc.py     # web3.py facade, read-only
├── clients/etherscan.py
├── tools/             # one module per tool group; each exposes register(server)
├── formatting.py      # exact decimal strings, JSON-safe conversion
└── metrics.py         # Prometheus instrumentation decorator
tests/                 # fake Web3, httpx MockTransport, in-memory MCP client, ADR-0001 guard
```
