# Invoke in a separate PowerShell process; never put a password in this file.
$ErrorActionPreference = 'Stop'
$secret = Read-Host 'Password for infoexplorer_app (hidden)' -AsSecureString
try {
    $env:MYSQL_HOST = '127.0.0.1'
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'infoexplorer'
    $env:MYSQL_USER = 'infoexplorer_app'
    $env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new('', $secret).Password
    Push-Location $PSScriptRoot
    try {
        New-Item -ItemType Directory -Path target -Force | Out-Null
        # A fresh E-drive directory avoids ownership conflicts between elevated
        # and ordinary Windows sessions. Do not alter shared TEMP permissions.
        $runtimeTemp = Join-Path $PSScriptRoot ('target\runtime-temp\' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $runtimeTemp -Force | Out-Null
        $jvmArguments = '-Dspring-boot.run.jvmArguments=-Dspring.devtools.restart.enabled=false -Djava.io.tmpdir="' + $runtimeTemp + '"'
        Write-Host 'Starting Java with MySQL: infoexplorer_app / infoexplorer on 127.0.0.1:3306. Stop with Ctrl+C.'
        & .\mvnw.cmd spring-boot:run '-Dspring-boot.run.profiles=mysql' $jvmArguments 2>&1 |
            Tee-Object -FilePath target/mysql-startup.log
        if ($LASTEXITCODE -ne 0) { throw 'Java startup/run failed; see target/mysql-startup.log.' }
    } finally { Pop-Location }
} finally {
    $secret.Dispose()
    Remove-Item Env:MYSQL_PASSWORD,Env:MYSQL_USER,Env:MYSQL_HOST,Env:MYSQL_PORT,Env:MYSQL_DATABASE -ErrorAction SilentlyContinue
}
