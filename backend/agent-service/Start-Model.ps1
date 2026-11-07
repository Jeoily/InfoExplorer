# Run in a separate PowerShell process. Never put a key in this file.
param([switch]$EnablePlanning)
$ErrorActionPreference = 'Stop'
$secret = Read-Host 'Agnes API key (hidden)' -AsSecureString
try {
    if ($secret.Length -eq 0) { throw 'API key is required.' }
    $env:MODEL_BASE_URL = 'https://api.agnes-ai.cn/v1'
    $env:MODEL_ALLOWED_HOST = 'api.agnes-ai.cn'
    $env:MODEL_NAME = 'agnes-2.5-flash'
    $env:MODEL_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
    $env:INFOEXPLORER_MODEL_ENABLED = 'true'
    $env:INFOEXPLORER_PLANNING_ENABLED = if ($EnablePlanning) { 'true' } else { 'false' }
    Push-Location $PSScriptRoot
    try {
        Write-Host 'Starting local Python service with Agnes agnes-2.5-flash. Requests may call the provider. Stop with Ctrl+C.'
        if ($EnablePlanning) { Write-Host 'Planning enabled: at most one planning call plus one report call per attempt; up to three Wikipedia searches. Verify provider pricing before use.' }
        & .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
        if ($LASTEXITCODE -ne 0) { throw 'Python service exited with an error.' }
    } finally { Pop-Location }
} finally {
    $secret.Dispose()
    Remove-Item Env:MODEL_API_KEY,Env:MODEL_BASE_URL,Env:MODEL_ALLOWED_HOST,Env:MODEL_NAME,Env:INFOEXPLORER_MODEL_ENABLED,Env:INFOEXPLORER_PLANNING_ENABLED -ErrorAction SilentlyContinue
}
