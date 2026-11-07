# Run in your own PowerShell. Secrets are entered interactively, never command arguments or files.
$ErrorActionPreference = 'Stop'
$mysqlUser = Read-Host 'MySQL username (press Enter for root)'
if ([string]::IsNullOrWhiteSpace($mysqlUser)) { $mysqlUser = 'root' }
$mysqlPort = Read-Host 'MySQL port (press Enter for 3306)'
if ([string]::IsNullOrWhiteSpace($mysqlPort)) { $mysqlPort = '3306' }
if ($mysqlPort -notmatch '^\d{1,5}$' -or [int]$mysqlPort -lt 1 -or [int]$mysqlPort -gt 65535) { throw 'Invalid port' }
$secret = Read-Host 'MySQL password (hidden)' -AsSecureString
try {
    $env:MYSQL_USER = $mysqlUser
    $env:MYSQL_PORT = $mysqlPort
    $env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new('', $secret).Password
    $env:INFOEXPLORER_MYSQL_TEST = '1'
    Push-Location $PSScriptRoot
    try {
        # The test can only create/drop its own fresh random infoexplorer_test_<uuid> schemas.
        & .\mvnw.cmd -o '-Dtest=MySqlIntegrationTests' test *> target/mysql-live-test.log
        $result = $LASTEXITCODE
        Get-Content target/mysql-live-test.log -Tail 18
        if ($result -ne 0) { throw 'MySQL tests failed. See target/mysql-live-test.log.' }
        Write-Host 'MySQL tests passed. Test databases were removed. No development database was changed.'
    } finally { Pop-Location }
} finally {
    $secret.Dispose()
    Remove-Item Env:MYSQL_PASSWORD,Env:MYSQL_USER,Env:MYSQL_PORT,Env:INFOEXPLORER_MYSQL_TEST -ErrorAction SilentlyContinue
}
