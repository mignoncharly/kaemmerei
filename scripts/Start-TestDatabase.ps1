param(
    [ValidateSet("Native","Docker","Existing")][string]$Backend = "Native",
    [string]$Python = "python",
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\18\bin",
    [ValidateRange(1024,65535)][int]$Port = 55432
)
$ErrorActionPreference = "Stop"
switch ($Backend) {
    "Native" {
        & (Join-Path $PSScriptRoot "Start-NativeTestDatabase.ps1") -Python $Python -PostgresBin $PostgresBin -Port $Port
    }
    "Docker" {
        & (Join-Path $PSScriptRoot "Start-DockerTestDatabase.ps1")
    }
    "Existing" {
        if (-not $env:TEST_POSTGRES_ADMIN_URL) {
            throw "Existing mode requires an explicitly configured dedicated TEST_POSTGRES_ADMIN_URL. No installed service is selected automatically."
        }
        Write-Output "Using the explicitly configured dedicated verification endpoint. Test fixtures validate loopback/database targeting before creating synthetic databases."
    }
}
