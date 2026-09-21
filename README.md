# onchain-agent-platform

[![ci](https://github.com/yunoim/onchain-agent-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/yunoim/onchain-agent-platform/actions/workflows/ci.yml)

A read-only on-chain data platform for AI agents, and the infrastructure to run it on
Kubernetes reproducibly: one `terraform apply`, three containers, a local LLM, zero
cloud spend.

```
User -> Agent (FastAPI) -> LiteLLM gateway -> Ollama qwen3:8b (default) | Anthropic (optional)
             |
             +-> MCP server (9 read-only Ethereum tools) -> public JSON-RPC / Etherscan
Prometheus scrapes both services; Grafana shows tokens, cost, latency, tool calls.
```

## The problem this solves

An LLM cannot see a blockchain. Handing it raw RPC access is dangerous (it can be talked
into signing) and impractical (public nodes have no per-address history). This platform
gives an agent a **tool-shaped, read-only view of Ethereum** over the Model Context
Protocol, routes every model call through a **gateway that owns model policy and cost**,
and deploys the whole thing with **infrastructure that can be explained line by line**.

It is a portfolio project for a DevOps / AI platform engineer role. The goal was not a
product but a structure whose every decision can be defended in an interview; the
reasoning lives in [docs/adr](docs/adr/README.md) and the concepts learned along the way
in [docs/LEARNING.md](docs/LEARNING.md).

## What is here

| Layer | Deliverable | Where |
|---|---|---|
| MCP server | 9 read-only Ethereum tools (balances, blocks, gas, tx, ERC-20, bounded log scans, Etherscan history), stdio and streamable-http from one binary, 44 tests | [services/mcp-server](services/mcp-server/README.md) |
| Agent | FastAPI `/ask` with a bounded tool-calling loop, token and cost accounting, `/readyz` that checks its dependencies, 12 tests | [services/agent](services/agent/README.md) |
| AI gateway | LiteLLM proxy: model aliases, local-first routing with hosted fallback, rate limits; the agent never holds a provider key | [services/gateway/litellm/config.yaml](services/gateway/litellm/config.yaml) |
| Local stack | `docker compose` with health-gated startup | [docker-compose.yml](docker-compose.yml) |
| Kubernetes | One Helm chart: 3 Deployments, Ingress, ConfigMap, Secret or existingSecret, probes, non-root read-only containers, ServiceMonitors, alert rules, Grafana dashboard | [deploy/helm/onchain-agent-platform](deploy/helm/onchain-agent-platform) |
| Terraform | Cluster layer (kind, or EKS) and a shared platform module (ingress-nginx, kube-prometheus-stack, Secret, app chart) | [infra/terraform](infra/terraform) |
| Observability | kube-prometheus-stack, service `/metrics`, four alerts, provisioned dashboard | [deploy/observability](deploy/observability) |
| CI/CD | ruff, pytest, read-only guard, helm lint/template, terraform validate, images to GHCR | [.github/workflows/ci.yml](.github/workflows/ci.yml) |

## Design decisions worth asking about

| ADR | Decision | One-line why |
|---|---|---|
| [0001](docs/adr/0001-read-only-onchain-access.md) | Read-only by construction | No signing code exists; a grep in CI and in the tests keeps it that way |
| [0002](docs/adr/0002-two-tier-data-sources.md) | RPC for state, Etherscan for history | Public nodes have no address index; history degrades to a clear error without a key |
| [0003](docs/adr/0003-mcp-dual-transport.md) | One MCP server, two transports | Claude Desktop wants stdio; the cluster wants HTTP; one codebase serves both |
| [0004](docs/adr/0004-litellm-gateway.md) | All LLM calls through LiteLLM | Routing, fallbacks, limits and keys live in one place, not in every service |
| [0005](docs/adr/0005-terraform-layering.md) | Cluster layer / platform module split | The platform is the deployable unit; kind and EKS are interchangeable substrates |
| [0006](docs/adr/0006-image-delivery.md) | GHCR images, `kind load` locally | kind cannot see host images; CI publishes, local dev stays fast |
| [0007](docs/adr/0007-local-first-model-routing.md) | Ollama by default, hosted models optional | Zero-cost, offline demo; one env var switches to a hosted model |

## Run it

### Quickest: docker compose

Prerequisites: Docker Desktop, and [Ollama](https://ollama.com) on the host with the
default model:

```powershell
ollama pull qwen3:8b
```

```powershell
docker compose up --build -d
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo.ps1
```

No API keys needed. Copy `.env.example` to `.env` only for Etherscan history tools or a
hosted model. Stop with `docker compose down`.

### Kubernetes by hand: kind + Helm

Prerequisites: the above plus `kind`, `kubectl`, `helm`. Stop the compose stack first; the
cluster binds host ports 80 and 443.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\kind-up.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\kind-load.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\kind-deploy.ps1
```

Then http://agent.localtest.me/docs (`*.localtest.me` resolves to 127.0.0.1). Tear down
with `kind delete cluster --name onchain-agent`.

### One command: Terraform

Prerequisites: Docker Desktop, Ollama with `qwen3:8b`, `kind`, `terraform`. No manually
created cluster may exist (`kind delete cluster --name onchain-agent`).

```powershell
cd infra\terraform\local
```

```powershell
terraform init
```

```powershell
terraform apply -var use_local_images=false
```

One apply creates the kind cluster, installs ingress-nginx and kube-prometheus-stack,
writes the platform Secret, and installs the application chart pulling the public GHCR
images. About ten minutes on a laptop; then:

| Service | URL |
|---|---|
| Agent | http://agent.localtest.me (`/ask`, `/tools`, `/readyz`, `/metrics`, `/docs`) |
| Grafana | http://grafana.localtest.me (admin / `TF_VAR_grafana_admin_password`, default `admin`) |
| Prometheus | http://prometheus.localtest.me |

Omit `-var use_local_images=false` to use images you built locally (Terraform loads them
into the node). Optional variables via environment, never via committed tfvars:

```powershell
$env:TF_VAR_etherscan_api_key = "..."
```

Everything, cluster included, goes away with:

```powershell
terraform destroy
```

The AWS variant in [infra/terraform/aws-eks](infra/terraform/aws-eks/README.md) reuses the
platform module behind an NLB. It is validated in CI and planned by hand; it is never
applied automatically. Read its cost note (about $0.30 per hour) first.

## Demo

[docs/DEMO.md](docs/DEMO.md) walks through three questions with observed answers, what to
point at while each runs, and what to show in Grafana:

1. What is the ETH balance of vitalik.eth right now?
2. Find USDC transfers above 1,000,000 USDC in the last 300 blocks and list the three largest.
3. What is the current gas price in gwei and the latest block number?

All three answer through the gateway with the local model at $0.00; typical wall time is
20 to 70 seconds per question on an 8 GB laptop GPU.

## Completion criteria

| Criterion | Status |
|---|---|
| A fresh machine runs `terraform apply` once and the full stack is up on a local cluster | Verified: destroy then apply with GHCR images, see [LEARNING.md](docs/LEARNING.md#phase-6-wrap-up) |
| At least three demo questions answer through the gateway | Verified on compose, on kind via Helm, and on the Terraform-built cluster |
| The author can explain the Kubernetes, Terraform and Helm structure from [docs/LEARNING.md](docs/LEARNING.md) alone | Self-assessed after Phase 6 |

## Repository layout

```
services/
  mcp-server/          Python, mcp SDK 2.x, web3.py 8, uv, pytest, Dockerfile
  agent/               Python, FastAPI, openai SDK, mcp client, uv, pytest, Dockerfile
  gateway/litellm/     config.yaml (canonical; injected into compose and the chart)
deploy/
  kind/                cluster.yaml, ingress-nginx values for hostPort
  helm/onchain-agent-platform/   chart, values-local.yaml, dashboards/
  observability/       kube-prometheus-stack values
infra/terraform/
  modules/platform/    ingress-nginx, monitoring, Secret, app chart
  local/               kind cluster + platform (apply: yes)
  aws-eks/             VPC + EKS + platform (plan-only)
scripts/               kind-up/load/deploy, demo, register-claude-desktop, check-no-signing
docs/                  ARCHITECTURE.md, LEARNING.md, DEMO.md, adr/
```

## What I would do differently

See the retrospective at the end of [docs/LEARNING.md](docs/LEARNING.md#phase-6-wrap-up).

## License

MIT. See [LICENSE](LICENSE).
