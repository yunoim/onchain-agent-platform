# Demo script

Ten minutes, three questions, one dashboard. Everything below was run on the kind cluster
created by `terraform apply` with the local model (Ollama `qwen3:8b`); timings are from
an RTX 3070 Laptop (8 GB). Numbers such as balances and block heights change every run.

## 0. Before the demo

```powershell
kubectl -n onchain get pods
```

All three pods `1/1 Running`. Then confirm the agent's dependencies:

```powershell
Invoke-RestMethod http://agent.localtest.me/readyz
```

Expected: `ready: True`, `checks: mcp=ok gateway=ok`. If `gateway` is not ok, Ollama is
not running on the host (`ollama serve`).

Open two browser tabs: http://agent.localtest.me/docs and http://grafana.localtest.me
(admin / admin, folder `onchain-agent-platform`).

## 1. "What is the ETH balance of vitalik.eth right now?"

What to point at while it runs (about 20 to 60 s):

- The agent asks the gateway for a completion **with nine tool schemas attached**.
- The model answers with a tool call, not text: `get_eth_balance("vitalik.eth")`.
- The MCP server resolves the ENS name, calls `eth_getBalance`, returns an exact decimal
  string.
- The model turns that into prose; the agent strips the `<think>` block.

Observed answer (block 26026791):

> The ETH balance of vitalik.eth (0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045) is
> 6.712603153701629485 ETH as of block 26026791.

Response metadata: `iterations: 2`, `tool_calls: [get_eth_balance]`, about 3,600 tokens,
`estimated_cost_usd: 0.0`.

Talking point: the number comes from the RPC node, not the model. The system prompt
forbids re-deriving amounts, and the exact string is the authoritative field.

## 2. "Find USDC transfers above 1,000,000 USDC in the last 300 blocks and list the three largest."

About 45 to 70 s. One `eth_getLogs` call over 300 blocks returned roughly 29,000 Transfer
events; the MCP server filtered and sorted them so the model only saw the top matches.

Observed answer (blocks 26026494 to 26026793):

> 1. 200,000,000 USDC, block 26026715, 0x38AA... to 0xEe7a...
> 2. 30,000,000 USDC, block 26026512, ...
> 3. 20,000,000.003754 USDC, block 26026604, ...
> Total transfers scanned: 29,151. Matches: 340.

Talking points:

- The block range is capped at 2,000 (`MAX_LOG_BLOCK_RANGE`) so a free RPC endpoint never
  sees an unbounded query. This is the read-only platform's version of a rate limit.
- Tool output is truncated before it goes back to the model (`MAX_TOOL_RESULT_CHARS`);
  the tool already returns only the top `limit` rows, so nothing important is lost.
- An 8B model sometimes says "found 3" when it means "showing 3 of 340". The numbers are
  right; the phrasing is a model limitation, and the response's `tool_calls` field shows
  the raw truth.

## 3. "What is the current gas price in gwei and the latest block number?"

About 30 s, two tool calls in one round (`get_gas_price`, `get_block`).

Observed answer:

> The current gas price is 0.899954398 gwei (base fee), and the latest block number is
> 26026615.

Talking point: nobody pays gas here. Reads are free RPC calls; the gas price is a market
quote, like a stock ticker. ADR-0001 makes paying impossible by construction (no signing
code, no keys).

## 4. Grafana

Refresh the `onchain-agent-platform` dashboard:

- "Questions answered (24h)" moved by 3.
- "Tokens / min by model and kind" shows `local-default prompt` dominating: the nine tool
  schemas are resent every round-trip. That is the argument for terse tool descriptions.
- "Estimated LLM spend" stays at $0.00. Switch `LLM_MODEL` to `claude-default` with a key
  and this panel is where the decision becomes visible.
- Prometheus at http://prometheus.localtest.me/alerts lists four rules, all inactive.

## 5. Show the machinery, then tear it down

```powershell
terraform -chdir=infra\terraform\local state list
```

Six to nine resources: the cluster, the image-load step, two namespaces, two Secrets,
three Helm releases. Then:

```powershell
terraform -chdir=infra\terraform\local destroy
```

Everything, including the cluster, is gone in a few minutes; `terraform apply` brings it
back in about ten.

## If something goes wrong

| Symptom | Likely cause | Check |
|---|---|---|
| `readyz` says `gateway: error` | Ollama not running on the host | `curl http://localhost:11434/api/version` |
| `/ask` returns 502 | Gateway cannot reach the model | `kubectl -n onchain logs deploy/oap-onchain-agent-platform-litellm` |
| Answer takes minutes | GPU busy (image pulls, another model loaded) | `nvidia-smi`, `ollama ps` |
| History tools error | No Etherscan key (expected) | `TF_VAR_etherscan_api_key` then `terraform apply` |
| Grafana has no dashboard | Sidecar not yet synced | wait 60 s; `kubectl -n onchain get cm | grep dashboard` |
