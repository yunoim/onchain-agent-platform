# ADR-0003: One MCP server, two transports (stdio and streamable-http)

- Status: Accepted
- Date: 2026-09-21

## Context

The MCP server has two consumers with different connection models:

- Claude Desktop (Phase 1 verification) launches MCP servers as child
  processes and talks over **stdio**.
- The in-cluster agent (Phase 2 onward) reaches the server over the network
  as a separate Deployment, which requires an HTTP transport. MCP's current
  network transport is **streamable-http**; SSE is deprecated.

Maintaining two server implementations would duplicate tool code and let the
two drift.

## Decision

- Tool implementations live in `onchain_mcp/tools/` and are registered on a
  single `FastMCP` instance in `onchain_mcp/server.py`.
- A single CLI entry point, `onchain-mcp --transport {stdio,streamable-http}`,
  selects the transport at startup. Default is stdio (Claude Desktop friendly).
- The container image runs `--transport streamable-http --host 0.0.0.0
  --port 8000`. The Helm chart and docker compose only ever use HTTP.
- Health (`/healthz`) and Prometheus metrics (`/metrics`) are mounted on the
  same ASGI app when running over HTTP so Kubernetes probes and scraping do not
  need a second port.

## Consequences

- Positive: one test suite, one Dockerfile, one tool catalogue.
- Positive: the stdio path doubles as an offline smoke test with no cluster.
- Negative: stdio mode has no health endpoint; that is acceptable because the
  host process (Claude Desktop) supervises it.
- Note: streamable-http is stateful by default (session per client). The
  server is run stateless where possible so multiple replicas behind a Service
  work without sticky sessions. Recorded in LEARNING.md when we hit it.
