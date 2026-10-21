param(
    [string]$Python = "python",
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\18\bin",
    [ValidateRange(1024,65535)][int]$Port = 55432
)
$ErrorActionPreference = "Stop"
$manager = Join-Path $PSScriptRoot "native_test_database.py"
$configuration = & $Python $manager start --bin $PostgresBin --port $Port
if ($LASTEXITCODE -ne 0) { throw "Native PostgreSQL setup failed. See the specific error above. Existing cluster data is preserved; retry from an authorized PowerShell terminal if Windows denied access." }
$connection = $configuration | ConvertFrom-Json
if ($connection.backend -ne "native" -or -not $connection.passfile -or -not $connection.url) {
    throw "Native setup did not return valid connection configuration."
}
$env:TEST_POSTGRES_ADMIN_URL = $connection.url
$env:PGPASSFILE = $connection.passfile
Write-Output "Native test PostgreSQL ready on 127.0.0.1:$Port. TEST_POSTGRES_ADMIN_URL and PGPASSFILE configured for this terminal; Docker is not required."
