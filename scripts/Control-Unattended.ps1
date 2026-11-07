param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('status','check','python-start','python-stop','mysql-test','java-deploy','java-stop','shutdown')]
    [string]$Action,
    [switch]$NoWait
)
$ErrorActionPreference='Stop'
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$sessions=[IO.Path]::GetFullPath((Join-Path $project 'logs\unattended'))
$current=Get-Content -LiteralPath (Join-Path $sessions 'current.json') -Raw | ConvertFrom-Json
$session=[IO.Path]::GetFullPath($current.session)
if ([IO.Path]::GetDirectoryName($session) -ne $sessions -or [IO.Path]::GetFileName($session) -notmatch '^[a-f0-9]{32}$') {
    throw 'Invalid local session directory.'
}
if ($Action -eq 'status') {
    Get-Content -LiteralPath (Join-Path $session 'status.json') -Raw
    return
}
if (-not (Get-Process -Id $current.pid -ErrorAction SilentlyContinue)) {
    throw 'Preparation window is not running. Start-Unattended.ps1 requires local credential input again.'
}
$requestId=[guid]::NewGuid().ToString('N')
$requestPath=Join-Path $session ($requestId+'.request.json')
$temporaryPath=Join-Path $session ($requestId+'.writing')
$resultPath=Join-Path $session ($requestId+'.result.json')
@{id=$requestId;action=$Action}|ConvertTo-Json -Compress|Set-Content -LiteralPath $temporaryPath -Encoding UTF8
Move-Item -LiteralPath $temporaryPath -Destination $requestPath
Write-Host "Submitted $Action. Request: $requestId"
if ($NoWait) { return }
$until=(Get-Date).AddMinutes(10)
while (-not (Test-Path -LiteralPath $resultPath)) {
    if ((Get-Date) -gt $until) { throw 'Still waiting. Do not resubmit deployment; inspect status and this request result later.' }
    Start-Sleep -Milliseconds 500
}
$result=Get-Content -LiteralPath $resultPath -Raw
Write-Output $result
if (($result|ConvertFrom-Json).status -ne 'passed') { throw 'Operation did not pass. Inspect the displayed fixed error/log path before proceeding.' }
