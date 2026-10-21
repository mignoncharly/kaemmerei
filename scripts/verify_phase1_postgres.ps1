param(
    [string]$Python = "python",
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\18\bin"
)
$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$scratchRoot = Join-Path $projectRoot ".verification"
New-Item -ItemType Directory -Force -Path $scratchRoot | Out-Null
$runRoot = Join-Path $scratchRoot ("pg-run-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $runRoot | Out-Null
$clusterPath = Join-Path $runRoot "data"
$passwordPath = Join-Path $runRoot "auth.txt"
$serverLog = Join-Path $scratchRoot "phase1-postgres-server.log"
$password = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
[System.IO.File]::WriteAllText($passwordPath, $password, [System.Text.Encoding]::ASCII)
$previousAdmin = $env:TEST_POSTGRES_ADMIN_URL
$started = $false
$verificationExit = 1
try {
    & (Join-Path $PostgresBin "initdb.exe") -D $clusterPath --username=ohvr_verify --encoding=UTF8 --locale=C --auth-host=scram-sha-256 --auth-local=reject --pwfile=$passwordPath
    if ($LASTEXITCODE -ne 0) { throw "Disposable PostgreSQL initdb failed" }
    Remove-Item -LiteralPath $passwordPath -Force
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    & (Join-Path $PostgresBin "pg_ctl.exe") -D $clusterPath -l $serverLog -o "-h 127.0.0.1 -p $port" -w start
    if ($LASTEXITCODE -ne 0) { throw "Disposable PostgreSQL startup failed" }
    $started = $true
    $env:TEST_POSTGRES_ADMIN_URL = "postgresql+psycopg://ohvr_verify:${password}@127.0.0.1:${port}/postgres"
    Push-Location $projectRoot
    try {
        & $Python scripts/verify_phase1.py --database postgresql
        $verificationExit = $LASTEXITCODE
    } finally { Pop-Location }
} finally {
    $env:TEST_POSTGRES_ADMIN_URL = $previousAdmin
    if ($started) {
        & (Join-Path $PostgresBin "pg_ctl.exe") -D $clusterPath -m fast -w stop
        if ($LASTEXITCODE -ne 0) { throw "Could not stop disposable PostgreSQL; retained $runRoot for recovery" }
    }
    # Delete only this generated run directory, after stopping its own cluster.
    $resolvedRun = (Resolve-Path -LiteralPath $runRoot).Path
    $resolvedScratch = (Resolve-Path -LiteralPath $scratchRoot).Path
    if ([System.IO.Path]::GetDirectoryName($resolvedRun) -ne $resolvedScratch -or
        [System.IO.Path]::GetFileName($resolvedRun) -notmatch '^pg-run-[0-9a-f]{32}$') {
        throw "Refusing cleanup outside generated verification storage"
    }
    Remove-Item -LiteralPath $resolvedRun -Recurse -Force
}
exit $verificationExit
