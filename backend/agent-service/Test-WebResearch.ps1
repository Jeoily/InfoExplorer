param([switch]$WithExtraction)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Project Python environment not found.' }
$previousPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
$previousLiveSearch = [Environment]::GetEnvironmentVariable('INFOEXPLORER_LIVE_SEARCH', 'Process')
$previousModelEnabled = [Environment]::GetEnvironmentVariable('INFOEXPLORER_MODEL_ENABLED', 'Process')
Push-Location $PSScriptRoot
try {
    $env:INFOEXPLORER_LIVE_SEARCH = '0'
    $env:INFOEXPLORER_MODEL_ENABLED = 'false'
    $env:PYTHONPATH = $PSScriptRoot
    if ($WithExtraction) {
        $dependencyPath = Join-Path $PSScriptRoot '.web-deps'
        if (-not (Test-Path -LiteralPath (Join-Path $dependencyPath 'trafilatura'))) {
            throw 'Optional extraction dependencies are missing. See app/web_research/README.md.'
        }
        $env:PYTHONPATH = $dependencyPath + [IO.Path]::PathSeparator + $PSScriptRoot
    }
    $testFiles = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'tests') -Filter 'test_web_*.py' | ForEach-Object { $_.FullName })
    & $pythonPath -m pytest @testFiles -q
    if ($LASTEXITCODE -ne 0) { throw 'Web foundation tests failed; inspect the safe test output above.' }
    Write-Host 'Offline web tests finished. These are not live SearXNG, model, or database tests.'
} finally {
    [Environment]::SetEnvironmentVariable('PYTHONPATH', $previousPythonPath, 'Process')
    [Environment]::SetEnvironmentVariable('INFOEXPLORER_LIVE_SEARCH', $previousLiveSearch, 'Process')
    [Environment]::SetEnvironmentVariable('INFOEXPLORER_MODEL_ENABLED', $previousModelEnabled, 'Process')
    Pop-Location
}
