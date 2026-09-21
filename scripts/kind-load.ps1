# Build both service images and load them into the kind cluster (ADR-0006 local path).
#   powershell -ExecutionPolicy Bypass -File .\scripts\kind-load.ps1
# kind nodes run their own containerd and cannot see the host Docker daemon's images;
# `kind load docker-image` copies them across.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$cluster = "onchain-agent"

docker build -t onchain-mcp-server:dev (Join-Path $root "services\mcp-server")
if (-not $?) { exit 1 }
docker build -t onchain-agent:dev (Join-Path $root "services\agent")
if (-not $?) { exit 1 }

# Only the images built here. The LiteLLM image is pulled by kubelet: `kind load` of a
# multi-platform image fails with "content digest not found" because the host store lacks
# the other platforms' layers that `ctr import --all-platforms` asks for.
kind load docker-image onchain-mcp-server:dev onchain-agent:dev --name $cluster
if (-not $?) { exit 1 }

Write-Host "Images loaded into kind cluster '$cluster'." -ForegroundColor Green
