# ADR-0001 guard (Windows PowerShell 5.1 version of check-no-signing.sh).
# Fails if any signing / transaction-submission identifier appears in service sources.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$targets = @(
    (Join-Path $root "services\mcp-server\src"),
    (Join-Path $root "services\agent\src")
)

$pattern = '\beth_account\b|\bAccount\.|\bsign_transaction\b|\bsign_message\b|\bsignHash\b|\bsend_transaction\b|\bsend_raw_transaction\b|\beth_sendTransaction\b|\beth_sendRawTransaction\b|\bprivate_key\b|\bPRIVATE_KEY\b|\bmnemonic\b|\bconstruct_sign_and_send_raw_middleware\b|\bSignAndSendRawMiddlewareBuilder\b'

$hits = @()
foreach ($dir in $targets) {
    if (-not (Test-Path $dir)) { continue }
    $hits += Get-ChildItem -Path $dir -Recurse -Filter *.py | Select-String -Pattern $pattern
}

if ($hits.Count -gt 0) {
    $hits | ForEach-Object { Write-Host ("{0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim()) }
    Write-Error "signing-related identifiers found (see ADR-0001)."
    exit 1
}
Write-Host "OK: no signing code in service sources."
