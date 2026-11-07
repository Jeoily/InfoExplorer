$ErrorActionPreference = 'Stop'
$docker = 'E:\Applications\Docker\resources\bin\docker.exe'
if (-not (Test-Path -LiteralPath $docker)) { throw 'Docker executable not found at configured E drive location.' }
if (Test-Path Env:SEARXNG_SECRET) { throw 'SEARXNG_SECRET is already set; use a fresh PowerShell session.' }
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $rng.GetBytes($bytes)
    $env:SEARXNG_SECRET = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    & $docker compose -f (Join-Path $PSScriptRoot 'compose.yml') up -d
    if ($LASTEXITCODE -ne 0) { throw 'Search container startup failed.' }
} finally {
    Remove-Item Env:SEARXNG_SECRET -ErrorAction SilentlyContinue
    [Array]::Clear($bytes, 0, $bytes.Length)
    $rng.Dispose()
}
Write-Host 'Search container started; verify http://127.0.0.1:8888 before use.'
