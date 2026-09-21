#!/usr/bin/env bash
# Install or upgrade the platform chart on the kind cluster with locally loaded images.
# Secrets come from the environment or a .env file at the repo root.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART="$ROOT/deploy/helm/onchain-agent-platform"
NAMESPACE="${NAMESPACE:-onchain}"
RELEASE="${RELEASE:-oap}"

if [ -f "$ROOT/.env" ]; then
  set -a; . "$ROOT/.env"; set +a
fi

kubectl config use-context kind-onchain-agent >/dev/null

helm upgrade --install "$RELEASE" "$CHART" \
  --namespace "$NAMESPACE" --create-namespace \
  -f "$CHART/values-local.yaml" \
  --set-file litellm.config="$ROOT/services/gateway/litellm/config.yaml" \
  --set-string secrets.values.LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-local-dev-change-me}" \
  --set-string secrets.values.ETHERSCAN_API_KEY="${ETHERSCAN_API_KEY:-}" \
  --set-string secrets.values.ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  --wait --timeout 5m

echo
kubectl -n "$NAMESPACE" get pods -l "app.kubernetes.io/instance=$RELEASE"
echo
echo "Try: curl -s http://agent.localtest.me/readyz"
