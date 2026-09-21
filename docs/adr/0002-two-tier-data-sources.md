# ADR-0002: Two-tier data sources: JSON-RPC for state, Etherscan V2 for history

- Status: Accepted
- Date: 2026-09-21

## Context

The demo scenarios need two kinds of data:

- **Current state**: balance of an address, latest block, gas price, a
  transaction by hash, ERC-20 metadata. Standard JSON-RPC answers these in one
  call each.
- **Address history**: "all transactions of address X in the last month",
  "all token transfers to X". Ethereum nodes do not index by address; answering
  this over JSON-RPC means scanning blocks or issuing wide `eth_getLogs`
  queries, which free public RPC endpoints reject or throttle.

Running an indexer (e.g. a local archive node or a self-hosted indexer) is out
of scope for a portfolio project and costs money.

## Decision

- Tier 1, required: a public JSON-RPC endpoint (`ETH_RPC_URL`, default
  PublicNode). Used by web3.py for all state tools. Log scans are capped at
  2000 blocks per call so they stay inside free-tier limits.
- Tier 2, optional: Etherscan API V2 (`ETHERSCAN_API_KEY`, free tier, 5 req/s).
  Used only by the two address-history tools. If the key is absent, those tools
  return a structured error that tells the agent (and the user) exactly which
  key would unlock them. The rest of the server works unchanged.

## Consequences

- Positive: the platform runs with zero credentials for state queries, and
  fully with one free key. No paid infrastructure.
- Positive: the degradation is explicit and testable. Unit tests cover both
  "key present" and "key missing" branches.
- Negative: two upstream dependencies with different rate limits and failure
  modes. Both are wrapped in a thin client layer with retries and timeouts so
  the MCP tool surface stays uniform.
- Negative: Etherscan responses are indexed data, not chain truth. Tool
  descriptions state the source so the LLM can caveat its answers.
