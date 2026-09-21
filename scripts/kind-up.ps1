# Create the local kind cluster and install ingress-nginx (Windows PowerShell 5.1).
#   powershell -ExecutionPolicy Bypass -File .\scripts\kind-up.ps1
# Idempotent: re-running on an existing cluster only upgrades ingress-nginx.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$cluster = "onchain-agent"
$ingressChartVersion = "4.15.1"

$existing = kind get clusters 2>$null
if ($existing -contains $cluster) {
    Write-Host "kind cluster '$cluster' already exists; skipping create."
} else {
    kind create cluster --config (Join-Path $root "deploy\kind\cluster.yaml") --wait 120s
    if (-not $?) { exit 1 }
}

kubectl config use-context "kind-$cluster" | Out-Null

helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx 2>$null | Out-Null
helm repo update ingress-nginx | Out-Null
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx `
    --version $ingressChartVersion `
    --namespace ingress-nginx --create-namespace `
    -f (Join-Path $root "deploy\kind\ingress-nginx-values.yaml") `
    --wait --timeout 5m
if (-not $?) { exit 1 }

Write-Host ""
Write-Host "Cluster ready. Next: .\scripts\kind-load.ps1 then .\scripts\kind-deploy.ps1" -ForegroundColor Green
