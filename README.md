# onchain-agent-platform

> **Status: Phase 1 complete.** The MCP server works end-to-end against Ethereum
> mainnet over stdio and HTTP; see [services/mcp-server](services/mcp-server/README.md).
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
| AI gateway | LiteLLM proxy owning model aliases, routing, rate limits and spend logs; the agent never touches a provider key |
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
| 2 | Agent + LiteLLM, docker compose | next |
| 3 | kind + Helm chart | |
| 4 | Terraform (kind), then EKS module (plan) | |
| 5 | Observability + CI/CD | |
| 6 | Final README, demo script | |

## Quick start

Arrives with Phase 2 (docker compose) and Phase 4 (`terraform apply`).

## License

MIT. See [LICENSE](LICENSE).
