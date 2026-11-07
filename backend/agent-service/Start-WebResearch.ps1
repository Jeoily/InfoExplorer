# Starts only the opt-in public web extraction service; never enables a model.
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$webDeps = Join-Path $PSScriptRoot '.web-deps'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project Python environment is missing.' }
if (-not (Test-Path -LiteralPath (Join-Path $webDeps 'trafilatura'))) { throw 'Optional extraction dependency is missing. No packages were installed.' }
$names = @('PYTHONPATH', 'INFOEXPLORER_WEB_ENABLED', 'INFOEXPLORER_WEB_MODEL_ENABLED', 'INFOEXPLORER_MODEL_ENABLED', 'INFOEXPLORER_PLANNING_ENABLED')
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:PYTHONPATH = "$webDeps;$PSScriptRoot"
    $env:INFOEXPLORER_WEB_ENABLED = 'true'
    $env:INFOEXPLORER_WEB_MODEL_ENABLED = 'false'
    $env:INFOEXPLORER_MODEL_ENABLED = 'false'
    $env:INFOEXPLORER_PLANNING_ENABLED = 'false'
    Push-Location $PSScriptRoot
    try {
        Write-Host 'Starting loopback Python service. V2 uses public web retrieval; model disabled. Ctrl+C stops it.'
        & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
        if ($LASTEXITCODE -ne 0) { throw 'Python service exited unsuccessfully.' }
    } finally { Pop-Location }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}
