param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('status','start','stop','restart-python','rebuild-java','restart-frontend','shutdown')]
    [string]$Action
)
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
& (Join-Path $project 'backend\agent-service\.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'debug_env.py') $Action
if ($LASTEXITCODE -ne 0) { throw 'Debug action did not pass. Do not automatically resubmit an action that timed out.' }
