param(
    [switch]$LiveModel,
    [switch]$RecordPublic,
    [string]$BaseUrl,
    [string]$AllowedHost,
    [string]$Model,
    [ValidateRange(1,10)][int]$Attempts=1
)
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
$python=Join-Path $project 'backend\agent-service\.venv\Scripts\python.exe'
$arguments=@((Join-Path $PSScriptRoot 'debug_env.py'),'serve')
if ($RecordPublic) { $arguments+='--record-public' }
if ($LiveModel) {
    if (-not $BaseUrl -or -not $AllowedHost -or -not $Model) { throw 'Provide confirmed provider, host and model.' }
    $arguments+=@('--live-model','--base-url',$BaseUrl,'--allowed-host',$AllowedHost,'--model',$Model,'--attempts',"$Attempts")
}
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Debug manager stopped with an error; see the safe message above.' }
