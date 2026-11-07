param([string]$MavenPath)
$ErrorActionPreference = 'Stop'
$frontendRoot = $PSScriptRoot
$javaRoot = [IO.Path]::GetFullPath((Join-Path $frontendRoot '..\backend\java-api'))
if (-not $MavenPath) {
    $mavenCommand = Get-Command mvn.cmd -ErrorAction SilentlyContinue
    if ($mavenCommand) { $MavenPath = $mavenCommand.Source }
    else {
        $cached = Get-ChildItem -LiteralPath (Join-Path $env:USERPROFILE '.m2\wrapper\dists') -Filter mvn.cmd -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cached) { $MavenPath = $cached.FullName }
    }
}
if (-not $MavenPath -or -not (Test-Path -LiteralPath $MavenPath)) { throw 'Pass -MavenPath pointing to an installed mvn.cmd. No tools will be downloaded.' }
foreach ($port in @(18080,4173)) {
    $probe = [Net.Sockets.TcpClient]::new()
    try { $probe.Connect('127.0.0.1',$port); throw "Port $port is occupied. Stop its owner before running isolated tests." }
    catch [Net.Sockets.SocketException] { }
    finally { $probe.Dispose() }
}
$testJob = $null
Push-Location $frontendRoot
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    $testJob = Start-Job -ScriptBlock {
        param($projectRoot,$mavenExecutable)
        Set-Location $projectRoot
        $env:INFOEXPLORER_UI_PREVIEW = '1'
        & $mavenExecutable -o '-Dtest=UiPreviewTests' test *> target/react-ui-preview.log
        if ($LASTEXITCODE -ne 0) { throw 'Isolated Java preview failed; inspect target/react-ui-preview.log.' }
    } -ArgumentList $javaRoot,$MavenPath
    $ready=$false
    for ($i=0;$i -lt 60;$i++) {
        if ($testJob.State -in @('Failed','Completed','Stopped')) { throw 'Java preview exited before becoming ready.' }
        try { $response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:18080/actuator/health' -TimeoutSec 1; if ($response.StatusCode -eq 200) { $ready=$true;break } } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'Isolated Java preview did not become ready.' }
    & npm.cmd run test:e2e
    if ($LASTEXITCODE -ne 0) { throw 'Browser tests failed; inspect test-results.' }
} finally {
    if ($testJob) {
        Set-Content -LiteralPath (Join-Path $javaRoot 'target\ui-preview.stop') -Value 'browser-tests-finished'
        $finished=Wait-Job -Job $testJob -Timeout 90
        if ($finished) { Receive-Job -Job $testJob; Remove-Job -Job $testJob }
        else { Write-Warning 'Java preview has not stopped yet. Inspect the test job and log; do not start another backend on port 18080.' }
    }
    Pop-Location
}
