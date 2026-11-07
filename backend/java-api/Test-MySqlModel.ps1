# Run in a separate PowerShell process after starting the Python model service.
$ErrorActionPreference = 'Stop'
$mysqlUser = Read-Host 'MySQL username for temporary test databases (Enter for root)'
if ([string]::IsNullOrWhiteSpace($mysqlUser)) { $mysqlUser = 'root' }
$secret = Read-Host 'MySQL password (hidden)' -AsSecureString
try {
    $env:MYSQL_USER = $mysqlUser
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new('', $secret).Password
    $env:INFOEXPLORER_MYSQL_TEST = '1'
    $env:INFOEXPLORER_TEST_AGENT_MODE = 'live-model'
    $env:INFOEXPLORER_TEST_AGENT_URL = 'http://127.0.0.1:8000'
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 5
    if ($health.status -ne 'UP') { throw 'Python service is not ready.' }
    Push-Location $PSScriptRoot
    try {
        New-Item -ItemType Directory -Path target -Force | Out-Null
        & .\mvnw.cmd -o '-Dtest=MySqlLiveModelIntegrationTests' test *> target/mysql-model-test.log
        $result = $LASTEXITCODE
        Get-Content target/mysql-model-test.log -Tail 22
        if ($result -ne 0) { throw 'MySQL/model test failed. See target/mysql-model-test.log. No automatic retry.' }
        Write-Host 'Test command finished. Check the report for 1 test, 0 failures/errors/skips. No development database was changed.'
    } finally { Pop-Location }
} finally {
    $secret.Dispose()
    Remove-Item Env:MYSQL_PASSWORD,Env:MYSQL_USER,Env:MYSQL_PORT,Env:INFOEXPLORER_MYSQL_TEST,Env:INFOEXPLORER_TEST_AGENT_MODE,Env:INFOEXPLORER_TEST_AGENT_URL -ErrorAction SilentlyContinue
}
