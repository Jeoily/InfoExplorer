# Run in the user's own PowerShell. Passwords are entered locally, never written to arguments/files.
$ErrorActionPreference = 'Stop'
$mysqlBin = 'C:\Program Files\MySQL\MySQL Server 8.4\bin'
$dumpExe = Join-Path $mysqlBin 'mysqldump.exe'
if (-not (Test-Path -LiteralPath $dumpExe)) { throw 'MySQL 8.4 mysqldump.exe was not found.' }
$service = Get-Service -Name MySQL84 -ErrorAction Stop
if ($service.Status -ne 'Running') { throw 'Start the MySQL84 Windows service before continuing.' }
$probe = [Net.Sockets.TcpClient]::new()
try { $probe.Connect('127.0.0.1',8080); throw 'Port 8080 is already in use. Stop the Java application before backing up and migrating.' }
catch [Net.Sockets.SocketException] { }
finally { $probe.Dispose() }

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$backupDir = Join-Path $projectRoot 'backups\mysql'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backupFile = Join-Path $backupDir ('infoexplorer_' + $stamp + '_' + [guid]::NewGuid().ToString('N') + '.sql')
Write-Host 'Step 1/2: Backup ONLY local database infoexplorer. Enter your MySQL ROOT password at Enter password.'
Write-Host 'Do not run other applications that write this database or change its schema during this operation.'
# Native password prompt does not expose the password to this script or process arguments.
& $dumpExe --no-defaults --no-login-paths --host=127.0.0.1 --port=3306 --user=root --password --ssl-mode=REQUIRED --single-transaction --quick --no-tablespaces --set-gtid-purged=OFF --routines --events --triggers --default-character-set=utf8mb4 "--result-file=$backupFile" --databases infoexplorer
if ($LASTEXITCODE -ne 0) { throw "Backup failed. Java was NOT started. Keep the partial file for diagnosis: $backupFile" }
if (-not (Test-Path -LiteralPath $backupFile) -or (Get-Item -LiteralPath $backupFile).Length -eq 0) { throw 'Backup output is missing or empty. Java was NOT started.' }
$hash = (Get-FileHash -LiteralPath $backupFile -Algorithm SHA256).Hash
Set-Content -LiteralPath ($backupFile + '.sha256') -Value $hash -Encoding ASCII
New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'target') -Force | Out-Null
@{ database='infoexplorer'; host='127.0.0.1'; port=3306; backup=$backupFile; bytes=(Get-Item -LiteralPath $backupFile).Length; sha256=$hash; completedUtc=[DateTime]::UtcNow.ToString('o'); restoreVerified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'target\mysql-backup-status.json') -Encoding UTF8
Write-Host "Backup completed: $backupFile"
Write-Host 'This confirms export success and a checksum, not a restore rehearsal. Never upload this backup.'
Write-Host 'Step 2/2: Enter the PROJECT account password for infoexplorer_app (may differ from root).'
Write-Host 'Java will now apply pending Flyway migrations. If migration fails, stop and inspect; do not repair or restore automatically.'
& (Join-Path $PSScriptRoot 'Start-MySql.ps1')
