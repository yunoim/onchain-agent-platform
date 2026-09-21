# Architecture Decision Records

Each record captures one decision, the context that forced it, and the
consequences we accept. Records are immutable once accepted; a change is a new
ADR that supersedes the old one.

| # | Title | Status |
|---|---|---|
| [0001](0001-read-only-onchain-access.md) | On-chain access is read-only by construction | Accepted |
| [0002](0002-two-tier-data-sources.md) | Two-tier data sources: JSON-RPC for state, Etherscan V2 for history | Accepted |
| [0003](0003-mcp-dual-transport.md) | One MCP server, two transports (stdio and streamable-http) | Accepted |
| [0004](0004-litellm-gateway.md) | All LLM traffic goes through a LiteLLM proxy | Accepted |
| [0005](0005-terraform-layering.md) | Terraform is split into a cluster layer and a reusable platform module | Accepted |
| [0006](0006-image-delivery.md) | Images are delivered through GHCR; local builds use `kind load` | Accepted |
| [0007](0007-local-first-model-routing.md) | Local-first model routing: Ollama default, hosted models optional (amends 0004) | Accepted |

Template for new records:

```markdown
# ADR-NNNN: Title

- Status: Proposed | Accepted | Superseded by ADR-MMMM
- Date: YYYY-MM-DD

## Context
## Decision
## Consequences
```
