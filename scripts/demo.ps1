# Run the three demo questions against a running agent (Windows PowerShell 5.1).
#   docker compose up --build   (from the repository root), then:
#   powershell -ExecutionPolicy Bypass -File .\scripts\demo.ps1
param(
    [string]$AgentUrl = "http://localhost:8080",
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"

$questions = @(
    "What is the ETH balance of vitalik.eth right now?",
    "Find USDC transfers above 1,000,000 USDC in the last 300 blocks and list the three largest.",
    "What is the current gas price in gwei and the latest block number?"
)

Write-Host "Agent: $AgentUrl"
$ready = Invoke-RestMethod -Uri "$AgentUrl/readyz" -Method Get
Write-Host ("Ready: {0}  mcp={1}  gateway={2}" -f $ready.ready, $ready.checks.mcp, $ready.checks.gateway)

foreach ($q in $questions) {
    Write-Host ""
    Write-Host "Q: $q" -ForegroundColor Cyan
    $body = @{ question = $q }
    if ($Model -ne "") { $body.model = $Model }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-RestMethod -Uri "$AgentUrl/ask" -Method Post -ContentType "application/json" -Body ($body | ConvertTo-Json)
    $sw.Stop()
    Write-Host "A: $($r.answer)"
    $tools = ($r.tool_calls | ForEach-Object { $_.name }) -join ", "
    Write-Host ("   model={0} iterations={1} tools=[{2}] tokens={3} cost=`${4} time={5:N1}s" -f `
        $r.model, $r.iterations, $tools, $r.usage.total_tokens, $r.estimated_cost_usd, $sw.Elapsed.TotalSeconds) -ForegroundColor DarkGray
}
