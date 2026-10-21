# Starts only the project's dedicated Linux PostgreSQL test service.
# Requires an installed, running Docker Desktop using Linux containers.
$ErrorActionPreference = "Stop"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed. Install/start Docker Desktop from https://docs.docker.com/desktop/setup/install/windows-install/ and rerun. No Windows PostgreSQL service will be changed."
}
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$compose = Join-Path $projectRoot "compose.test.yml"
$previousBootstrap = $env:OHVR_TEST_BOOTSTRAP_PASSWORD
$env:OHVR_TEST_BOOTSTRAP_PASSWORD = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
$testPassword = [guid]::NewGuid().ToString("N")
try {
    $osType = & docker info --format '{{.OSType}}'
    if ($LASTEXITCODE -ne 0) { throw "Docker engine is not reachable. Start Docker Desktop, wait for readiness, and rerun." }
    if ($osType -ne "linux") { throw "The dedicated PostgreSQL test service requires Linux containers." }
    & docker compose -f $compose up -d --wait --wait-timeout 120
    if ($LASTEXITCODE -ne 0) { throw "Dedicated PostgreSQL startup failed. Check Docker Desktop and whether port 55432 is free." }
    $exists = & docker compose -f $compose exec -T postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'ohvr_verify'"
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect dedicated test-role state." }
    # Generated passwords contain only hex characters; identifiers are fixed.
    # Reassert restricted attributes on restart; never use the bootstrap superuser for tests.
    if (("$exists").Trim() -eq "1") {
        $roleSql = "ALTER ROLE ohvr_verify LOGIN CREATEDB NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '$testPassword';"
    } else {
        $roleSql = "CREATE ROLE ohvr_verify LOGIN CREATEDB NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '$testPassword';"
    }
    & docker compose -f $compose exec -T postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c $roleSql
    if ($LASTEXITCODE -ne 0) { throw "Could not provision restricted test role." }
    $env:TEST_POSTGRES_ADMIN_URL = "postgresql+psycopg://ohvr_verify:${testPassword}@127.0.0.1:55432/postgres"
    Write-Output "Dedicated test service ready on 127.0.0.1:55432. This process's TEST_POSTGRES_ADMIN_URL is configured; no credentials were written to the repository."
} finally {
    $env:OHVR_TEST_BOOTSTRAP_PASSWORD = $previousBootstrap
}
