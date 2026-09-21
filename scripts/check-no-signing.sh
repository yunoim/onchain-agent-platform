#!/usr/bin/env bash
# ADR-0001 guard: fail if any signing / transaction-submission identifier appears in
# service source code. Runs in CI and can be run locally. Mirrors
# services/mcp-server/tests/test_read_only_guarantee.py.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGETS=(
  "$ROOT/services/mcp-server/src"
  "$ROOT/services/agent/src"
)

PATTERN='\beth_account\b|\bAccount\.|\bsign_transaction\b|\bsign_message\b|\bsignHash\b|\bsend_transaction\b|\bsend_raw_transaction\b|\beth_sendTransaction\b|\beth_sendRawTransaction\b|\bprivate_key\b|\bPRIVATE_KEY\b|\bmnemonic\b|\bconstruct_sign_and_send_raw_middleware\b|\bSignAndSendRawMiddlewareBuilder\b'

status=0
for dir in "${TARGETS[@]}"; do
  [ -d "$dir" ] || continue
  if grep -rnE --include='*.py' "$PATTERN" "$dir"; then
    status=1
  fi
done

if [ "$status" -ne 0 ]; then
  echo "ERROR: signing-related identifiers found (see ADR-0001)." >&2
  exit 1
fi
echo "OK: no signing code in service sources."
