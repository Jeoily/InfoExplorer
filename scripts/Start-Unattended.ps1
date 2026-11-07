# Run in an ordinary PowerShell. No passwords or keys in command arguments.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root 'backend\agent-service\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project Python is missing.' }
& $python (Join-Path $PSScriptRoot 'unattended.py')
if ($LASTEXITCODE -ne 0) { throw 'Preparation stopped. Read the safe message above.' }
