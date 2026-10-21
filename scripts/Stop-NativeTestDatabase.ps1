param(
    [string]$Python = "python",
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\18\bin",
    [ValidateRange(1024,65535)][int]$Port = 55432
)
$ErrorActionPreference = "Stop"
& $Python (Join-Path $PSScriptRoot "native_test_database.py") stop --bin $PostgresBin --port $Port
if ($LASTEXITCODE -ne 0) { throw "Native test PostgreSQL stop failed; inspect the marked test cluster. Existing Windows services are not managed by this script." }
