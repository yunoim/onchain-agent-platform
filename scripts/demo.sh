#!/usr/bin/env bash
# Run the three demo questions against a running agent.
#   docker compose up --build   (from the repository root), then:  ./scripts/demo.sh
set -euo pipefail

AGENT_URL="${AGENT_URL:-http://localhost:8080}"
MODEL="${MODEL:-}"

questions=(
  "What is the ETH balance of vitalik.eth right now?"
  "Find USDC transfers above 1,000,000 USDC in the last 300 blocks and list the three largest."
  "What is the current gas price in gwei and the latest block number?"
)

echo "Agent: $AGENT_URL"
curl -sf "$AGENT_URL/readyz" || { echo "agent not ready"; exit 1; }
echo

for q in "${questions[@]}"; do
  echo
  echo "Q: $q"
  if [ -n "$MODEL" ]; then
    payload=$(printf '{"question": %s, "model": %s}' "$(printf '%s' "$q" | python -c 'import json,sys;print(json.dumps(sys.stdin.read()))')" "\"$MODEL\"")
  else
    payload=$(printf '{"question": %s}' "$(printf '%s' "$q" | python -c 'import json,sys;print(json.dumps(sys.stdin.read()))')")
  fi
  start=$(date +%s)
  curl -sf "$AGENT_URL/ask" -H 'Content-Type: application/json' -d "$payload" \
    | python -c '
import json,sys
r=json.load(sys.stdin)
print("A:", r["answer"])
tools = ", ".join(t["name"] for t in r["tool_calls"])
u = r["usage"]["total_tokens"]
print("   model=%s iterations=%s tools=[%s] tokens=%s cost=$%s" % (r["model"], r["iterations"], tools, u, r["estimated_cost_usd"]))'
  echo "   time=$(( $(date +%s) - start ))s"
done
