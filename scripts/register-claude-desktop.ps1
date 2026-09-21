# Register the onchain MCP server in Claude Desktop (Windows PowerShell 5.1).
#
# Claude Desktop rewrites claude_desktop_config.json from memory when it exits, so any
# edit made while the app is running is lost. This script therefore refuses to run while
# Claude is open. Sequence: quit Claude Desktop -> run this -> start Claude Desktop.
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File .\scripts\register-claude-desktop.ps1
# Optional:
#   -EtherscanApiKey <key>   enable the address-history tools
#   -Remove                  unregister the server instead
param(
    [string]$EtherscanApiKey = "",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

if (Get-Process -Name claude -ErrorAction SilentlyContinue) {
    Write-Host "Claude Desktop is running. Quit it completely (tray icon > Quit), then run this again." -ForegroundColor Yellow
    exit 1
}

$repoRoot   = Split-Path -Parent $PSScriptRoot
$serverDir  = Join-Path $repoRoot "services\mcp-server"
$configPath = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"

if (-not (Test-Path $configPath)) {
    Write-Host "Config not found at $configPath. Is Claude Desktop installed?" -ForegroundColor Red
    exit 1
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($null -eq $uv) {
    Write-Host "uv not found on PATH. Install from https://docs.astral.sh/uv/ and retry." -ForegroundColor Red
    exit 1
}

$backup = "$configPath.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
Copy-Item $configPath $backup

$config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json

if (-not ($config.PSObject.Properties.Name -contains "mcpServers")) {
    $config | Add-Member -MemberType NoteProperty -Name mcpServers -Value ([pscustomobject]@{})
}

if ($Remove) {
    if ($config.mcpServers.PSObject.Properties.Name -contains "onchain") {
        $config.mcpServers.PSObject.Properties.Remove("onchain")
    }
} else {
    $entry = [pscustomobject]@{
        command = $uv.Source
        args    = @("--directory", $serverDir, "run", "onchain-mcp")
        env     = [pscustomobject]@{
            ETH_RPC_URL       = "https://ethereum-rpc.publicnode.com"
            ETHERSCAN_API_KEY = $EtherscanApiKey
        }
    }
    if ($config.mcpServers.PSObject.Properties.Name -contains "onchain") {
        $config.mcpServers.onchain = $entry
    } else {
        $config.mcpServers | Add-Member -MemberType NoteProperty -Name onchain -Value $entry
    }
}

# Depth must exceed the nesting of Claude's own preference tree.
$json = $config | ConvertTo-Json -Depth 100
[System.IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "Backup : $backup"
Write-Host "Written: $configPath"
if ($Remove) {
    Write-Host "Removed mcpServers.onchain. Start Claude Desktop."
} else {
    Write-Host "Registered mcpServers.onchain -> $($uv.Source) --directory $serverDir run onchain-mcp"
    Write-Host "Start Claude Desktop, open a new chat, and check the tools menu for 'onchain'."
}
