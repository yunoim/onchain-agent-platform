# ADR-0004: All LLM traffic goes through a LiteLLM proxy

- Status: Accepted
- Date: 2026-09-21

## Context

Calling a provider SDK directly from the agent couples application code to a
vendor, spreads API keys across services, and leaves rate limiting and cost
tracking to be reimplemented per service. An AI platform role expects the
opposite: a central gateway that owns model policy.

Options considered: LiteLLM Proxy (open source, OpenAI-compatible, provider
routing built in), Portkey / Helicone (hosted, adds an external dependency),
a hand-written FastAPI proxy (educational but reinvents routing and retries).

## Decision

- Run the official `ghcr.io/berriai/litellm` image as the only egress to LLM
  providers. Provider keys (`ANTHROPIC_API_KEY`) are mounted **only** into the
  gateway pod.
- The agent uses the `openai` Python SDK pointed at `LLM_BASE_URL` with the
  LiteLLM master key. It requests a **model alias** (`claude-default`,
  `claude-fast`, `local-fallback`), never a provider model id.
- `services/gateway/litellm/config.yaml` defines aliases, the provider mapping
  (Anthropic primary, Ollama optional fallback), per-key rate limits, and
  enables spend logging. Model upgrades become a config change, not a code
  change.
- Token and cost metrics for Prometheus are emitted by the **agent** from the
  `usage` field of each response. LiteLLM's own Prometheus callback is an
  enterprise feature and is not relied upon.

## Consequences

- Positive: swapping or A/B testing models needs no agent redeploy.
- Positive: one place to add budgets, caching, or fallbacks later.
- Negative: an extra network hop and an extra Deployment to operate. Accepted
  because operating the gateway *is* the point of the exercise.
- Negative: the LiteLLM image is large (about 1 GB). kind pulls it once; fine
  locally.
