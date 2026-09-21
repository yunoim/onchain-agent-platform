#!/usr/bin/env bash
# Build both service images and load them into the kind cluster (ADR-0006 local path).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="onchain-agent"

docker build -t onchain-mcp-server:dev "$ROOT/services/mcp-server"
docker build -t onchain-agent:dev "$ROOT/services/agent"
# Only the images built here. The LiteLLM image is pulled by kubelet: `kind load` of a
# multi-platform image fails with "content digest not found" because the host store lacks
# the other platforms' layers that `ctr import --all-platforms` asks for.
kind load docker-image onchain-mcp-server:dev onchain-agent:dev --name "$CLUSTER"

echo "Images loaded into kind cluster '$CLUSTER'."
