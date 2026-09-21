# onchain-agent-platform

> **Status: Phase 4 complete.** One `terraform apply` creates a kind cluster, installs
> ingress-nginx and the platform chart, and the three demo questions are answered at
> `http://agent.localtest.me` by a local model (Ollama `qwen3:8b`) at zero cost. The same
> platform module targets AWS EKS (validated, plan-only). Observability and CI follow in Phase 5.
> Progress is tracked in [CLAUDE.md](CLAUDE.md); the full design is in
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

A read-only on-chain data platform for AI agents, and the infrastructure to run
it on Kubernetes reproducibly.

```
User -> AI Agent (FastAPI) -> LiteLLM Gateway -> Anthropic
             |
             +-> MCP Server (FastMCP, read-only) -> Ethereum RPC / Etherscan
```

## What this repository demonstrates

| Area | Deliverable |
|---|---|
| MCP | An `MCPServer` (mcp SDK 2.x) exposing 9 read-only Ethereum tools, tested with a fake RPC, usable from Claude Desktop (stdio) and from the cluster (streamable-http) |
| Agent | A FastAPI service that answers natural-language questions by driving those tools through a bounded tool-calling loop |
| AI gateway | LiteLLM proxy owning model aliases, routing, fallbacks and rate limits; local Ollama by default, hosted models by adding a key; the agent never touches a provider key |
| Kubernetes | Helm chart for the three services, ingress-nginx, `*.localtest.me` hostnames on a kind cluster |
| Terraform | `infra/terraform/local`: one `apply` creates the kind cluster and installs everything. `infra/terraform/aws-eks`: the same platform module on EKS, plan-only by default |
| Observability | kube-prometheus-stack, service `/metrics`, Grafana dashboard with LLM token and cost panels |
| CI/CD | GitHub Actions: lint, unit tests, image build and push to GHCR, `helm lint`, `terraform validate` |

## Design principles

1. **Read-only by construction.** No signing code exists anywhere in the tree.
   [ADR-0001](docs/adr/0001-read-only-onchain-access.md)
2. **Runs on free tiers.** Public RPC for state, a free Etherscan key for
   history, and a local kind cluster. [ADR-0002](docs/adr/0002-two-tier-data-sources.md)
3. **Explainable infrastructure.** Every non-obvious choice has an ADR; every
   Kubernetes / Terraform concept used is written up in
   [docs/LEARNING.md](docs/LEARNING.md).

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository layout, architecture, ADRs | done |
| 1 | MCP server + tests, Claude Desktop connection | done |
| 2 | Agent + LiteLLM, docker compose | done |
| 3 | kind + Helm chart | done |
| 4 | Terraform (kind), then EKS module (plan) | done |
| 5 | Observability + CI/CD | next |
| 6 | Final README, demo script | |

## Quick start (local, docker compose)

Prerequisites: Docker Desktop, and [Ollama](https://ollama.com) running on the host with
the default model pulled:

```powershell
ollama pull qwen3:8b
```

Start the stack (no API keys needed; copy `.env.example` to `.env` only if you want
Etherscan history tools or a hosted model):

```powershell
docker compose up --build -d
```

Ask the three demo questions:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo.ps1
```

Or one question by hand:

```powershell
Invoke-RestMethod -Uri http://localhost:8080/ask -Method Post -ContentType "application/json" -Body '{"question":"What is the ETH balance of vitalik.eth?"}'
```

| Service | URL |
|---|---|
| Agent | http://localhost:8080 (`/ask`, `/tools`, `/readyz`, `/metrics`, `/docs`) |
| LiteLLM gateway | http://localhost:4000 (OpenAI-compatible, key `LITELLM_MASTER_KEY`) |
| MCP server | http://localhost:8000 (`/mcp`, `/healthz`, `/metrics`) |

Stop everything:

```powershell
docker compose down
```

## Kubernetes (local kind cluster + Helm)

Prerequisites: the above plus `kind`, `kubectl`, `helm`. Stop the compose stack first if it
is running (`docker compose down`); the cluster binds host ports 80 and 443.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\kind-up.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\kind-load.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\kind-deploy.ps1
```

The three scripts create the cluster and install ingress-nginx, build and load the two
service images, and install the chart in `deploy/helm/onchain-agent-platform` as release
`oap` in namespace `onchain`. Then:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo.ps1 -AgentUrl http://agent.localtest.me
```

```powershell
helm -n onchain test oap
```

`*.localtest.me` resolves to 127.0.0.1, so `http://agent.localtest.me/docs`,
`http://litellm.localtest.me/health/liveliness` and `http://mcp.localtest.me/healthz` work
without editing a hosts file. Tear down with:

```powershell
kind delete cluster --name onchain-agent
```

## One command: Terraform (kind cluster + everything on it)

Prerequisites: Docker Desktop, Ollama with `qwen3:8b`, `kind`, `terraform`, and the two
service images built locally (`docker compose build` or `scripts/kind-load.ps1` builds
them; Terraform loads them into the cluster). Remove any manually created cluster first
(`kind delete cluster --name onchain-agent`).

```powershell
cd infra\terraform\local
```

```powershell
terraform init
```

```powershell
terraform apply
```

One apply creates the kind cluster, installs ingress-nginx, writes the platform Secret
from `TF_VAR_*` variables (all have local defaults), and installs the application chart.
Then `http://agent.localtest.me/readyz` should report ready. Optional secrets:

```powershell
$env:TF_VAR_etherscan_api_key = "..."
```

Tear everything down, cluster included:

```powershell
terraform destroy
```

The AWS variant lives in [infra/terraform/aws-eks](infra/terraform/aws-eks/README.md). It
shares the same platform module and is validated in CI but never applied automatically:
read its cost note first.

## License

MIT. See [LICENSE](LICENSE).
