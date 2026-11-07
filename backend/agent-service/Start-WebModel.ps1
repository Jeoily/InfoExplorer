# Explicit provider configuration; never pass a key as a parameter or save it here.
param(
    [Parameter(Mandatory=$true)][string]$BaseUrl,
    [Parameter(Mandatory=$true)][string]$AllowedHost,
    [Parameter(Mandatory=$true)][string]$Model
)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$webDeps = Join-Path $PSScriptRoot '.web-deps'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project Python environment is missing.' }
if (-not (Test-Path -LiteralPath (Join-Path $webDeps 'trafilatura'))) { throw 'Extraction dependency is missing.' }
$names = @('PYTHONPATH','MODEL_BASE_URL','MODEL_ALLOWED_HOST','MODEL_NAME','MODEL_API_KEY',
    'INFOEXPLORER_WEB_ENABLED','INFOEXPLORER_WEB_MODEL_ENABLED','INFOEXPLORER_MODEL_ENABLED','INFOEXPLORER_PLANNING_ENABLED','INFOEXPLORER_MODEL_DIAGNOSTICS')
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
$secret = Read-Host 'Provider API key (hidden; verify provider pricing before use)' -AsSecureString
try {
    if ($secret.Length -eq 0) { throw 'API key is required.' }
    $env:MODEL_BASE_URL = $BaseUrl
    $env:MODEL_ALLOWED_HOST = $AllowedHost
    $env:MODEL_NAME = $Model
    $env:MODEL_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
    $env:PYTHONPATH = "$webDeps;$PSScriptRoot"
    $env:INFOEXPLORER_WEB_ENABLED = 'true'
    $env:INFOEXPLORER_WEB_MODEL_ENABLED = 'true'
    $env:INFOEXPLORER_MODEL_DIAGNOSTICS = 'true'
    $env:INFOEXPLORER_MODEL_ENABLED = 'false'
    $env:INFOEXPLORER_PLANNING_ENABLED = 'false'
    Push-Location $PSScriptRoot
    try {
        & $python -c "from app.web_research.model_completion import JsonCompletion; JsonCompletion.from_env(); print('Model configuration shape validated; no network request made.')"
        if ($LASTEXITCODE -ne 0) { throw 'Model configuration is invalid.' }
        Write-Host 'Only explicitly selected web-model tasks call the provider (up to 3 calls per attempt). Ctrl+C stops the service.'
        & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
        if ($LASTEXITCODE -ne 0) { throw 'Python service exited unsuccessfully.' }
    } finally { Pop-Location }
} finally {
    $secret.Dispose()
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
}
