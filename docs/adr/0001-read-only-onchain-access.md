# ADR-0001: On-chain access is read-only by construction

- Status: Accepted
- Date: 2026-09-21

## Context

The platform exposes Ethereum data to an LLM-driven agent. An agent that can
sign or broadcast transactions is a liability: prompt injection through
on-chain data (token names, calldata, ENS text records) could steer it into
moving funds. The project also has no product need for writes; every demo
scenario is analytical.

## Decision

1. The MCP server exposes **only** query tools. There is no tool that accepts a
   private key, mnemonic, signed payload, or that calls `eth_sendTransaction` /
   `eth_sendRawTransaction`.
2. The codebase never imports `eth_account`, `web3.middleware.signing`, or any
   signer construction helper. A CI grep (`scripts/check-no-signing.sh`) fails
   the build if these identifiers appear outside that script.
3. No configuration key for a private key exists in `.env.example`, Helm
   values, or Terraform variables. The absence is structural, not a runtime flag.
4. Tools that scan logs or fetch history are bounded (block ranges, result
   limits) so the read path cannot be abused as a denial-of-service vector
   against free-tier RPC providers either.

## Consequences

- Positive: the threat model reduces to "leaked API keys" and "wrong answers".
  Both are recoverable. There is no irreversible action anywhere in the stack.
- Positive: a reviewer can verify the guarantee with a single grep instead of
  auditing control flow.
- Negative: the platform cannot be extended into a trading or automation agent
  without revisiting this ADR. That is intended.
