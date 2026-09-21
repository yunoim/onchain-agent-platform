# ADR-0007: Local-first model routing (Ollama default, hosted models optional)

- Status: Accepted
- Date: 2026-09-21
- Amends: [ADR-0004](0004-litellm-gateway.md) (which assumed Anthropic primary, Ollama fallback)

## Context

ADR-0004 fixed *where* model policy lives (the LiteLLM gateway) but assumed a hosted
provider would be the primary model. When Phase 2 started, the decision was made to run
without any provider key: the developer machine has an RTX 3070 (8 GB) and `qwen3:8b`,
which supports OpenAI-style tool calling, and a portfolio stack that costs nothing and
runs offline is easier to demo and to reproduce.

The alias mechanism from ADR-0004 makes this a configuration change, not a design change.

## Decision

- `local-default` (Ollama `qwen3:8b` on the host, reached from containers via
  `host.docker.internal`) is the default alias and what the agent requests unless told
  otherwise. Cost is reported as zero.
- `claude-default` and `claude-fast` remain defined. They work as soon as
  `ANTHROPIC_API_KEY` is present in the gateway's environment; without it the router's
  fallback rule sends the request to `local-default`, so a caller asking for a hosted
  model still gets an answer.
- Ollama runs on the host, not in a container: GPU passthrough inside Docker Desktop on
  Windows adds setup friction that buys nothing for this project. In Kubernetes (Phase 3)
  the same alias points at whatever `OLLAMA_BASE_URL` the cluster is given.
- Local-model quirks are handled in the agent, not the gateway: `<think>` reasoning blocks
  are stripped from answers; tool results are truncated before they go back to the model;
  `num_ctx` is raised to 12k so tool schemas plus results fit.

## Consequences

- Positive: `docker compose up` needs no secrets. Every demo question runs end to end at
  zero marginal cost.
- Positive: switching to a hosted model for quality comparison is one environment
  variable (`LLM_MODEL=claude-default`) plus a key; no code or image changes.
- Negative: an 8B model is slower and less reliable at multi-step tool use than a hosted
  frontier model. The bounded loop and the forced final answer exist partly for this.
- Negative: the stack now has an out-of-band dependency (a running Ollama on the host).
  The agent's `/readyz` reports the gateway, and the gateway health reports the model,
  so the failure is visible rather than silent.
