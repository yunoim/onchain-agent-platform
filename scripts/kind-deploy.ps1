# Install or upgrade the platform chart on the kind cluster (Windows PowerShell 5.1).
#   powershell -ExecutionPolicy Bypass -File .\scripts\kind-deploy.ps1
# Uses the locally loaded images (values-local.yaml) and injects the canonical LiteLLM
# config from services/gateway/litellm/config.yaml so it is never duplicated.
# Secrets: reads ETHERSCAN_API_KEY / ANTHROPIC_API_KEY / LITELLM_MASTER_KEY from the
# environment (or a .env file at the repo root) and passes them as chart values.
param(
    [string]$Namespace = "onchain",
    [string]$Release = "oap"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$chart = Join-Path $root "deploy\helm\onchain-agent-platform"

# Load .env if present (KEY=VALUE lines, no export keyword).
$dotenv = Join-Path $root ".env"
if (Test-Path $dotenv) {
    Get-Content $dotenv | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$' -and -not $_.StartsWith("#")) {
            if (-not (Test-Path "env:$($matches[1])")) { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
        }
    }
}

$masterKey = if ($env:LITELLM_MASTER_KEY) { $env:LITELLM_MASTER_KEY } else { "sk-local-dev-change-me" }
$etherscan = if ($env:ETHERSCAN_API_KEY) { $env:ETHERSCAN_API_KEY } else { "" }
$anthropic = if ($env:ANTHROPIC_API_KEY) { $env:ANTHROPIC_API_KEY } else { "" }

kubectl config use-context "kind-onchain-agent" | Out-Null

helm upgrade --install $Release $chart `
    --namespace $Namespace --create-namespace `
    -f (Join-Path $chart "values-local.yaml") `
    --set-file litellm.config=(Join-Path $root "services\gateway\litellm\config.yaml") `
    --set-string secrets.values.LITELLM_MASTER_KEY=$masterKey `
    --set-string secrets.values.ETHERSCAN_API_KEY=$etherscan `
    --set-string secrets.values.ANTHROPIC_API_KEY=$anthropic `
    --wait --timeout 5m
if (-not $?) { exit 1 }

Write-Host ""
kubectl -n $Namespace get pods -l "app.kubernetes.io/instance=$Release"
Write-Host ""
Write-Host "Try: Invoke-RestMethod http://agent.localtest.me/readyz" -ForegroundColor Green
