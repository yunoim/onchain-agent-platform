#!/usr/bin/env bash
# Create the local kind cluster and install ingress-nginx. Idempotent.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="onchain-agent"
INGRESS_CHART_VERSION="4.15.1"

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  echo "kind cluster '$CLUSTER' already exists; skipping create."
else
  kind create cluster --config "$ROOT/deploy/kind/cluster.yaml" --wait 120s
fi

kubectl config use-context "kind-$CLUSTER" >/dev/null

helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null 2>&1 || true
helm repo update ingress-nginx >/dev/null
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --version "$INGRESS_CHART_VERSION" \
  --namespace ingress-nginx --create-namespace \
  -f "$ROOT/deploy/kind/ingress-nginx-values.yaml" \
  --wait --timeout 5m

echo
echo "Cluster ready. Next: scripts/kind-load.sh then scripts/kind-deploy.sh"
