param(
    [string]$Python = "py",
    [ValidateSet("Native","Docker","Existing")][string]$DatabaseBackend = "Native",
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\18\bin",
    [ValidateRange(1024,65535)][int]$PostgresPort = 55432,
    [switch]$Push
)
$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$testPython = Join-Path $projectRoot ".venv-test\Scripts\python.exe"

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Executable (exit $LASTEXITCODE). Fix the reported error, then rerun this setup command." }
}

Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $testPython)) {
        if ($Python -eq "py") {
            Invoke-Checked -Executable $Python -Arguments @("-3.14", "-m", "venv", ".venv-test")
        } else {
            Invoke-Checked -Executable $Python -Arguments @("-m", "venv", ".venv-test")
        }
    }
    # Honor the user's approved package/proxy configuration; do not override it.
    Invoke-Checked -Executable $testPython -Arguments @("-m", "pip", "install", "-r", "requirements-dev.txt")
    Invoke-Checked -Executable $testPython -Arguments @("scripts/verify_phase1.py", "--database", "sqlite")
    Invoke-Checked -Executable $testPython -Arguments @("-m", "pytest", "-q", "--database", "sqlite", "--junitxml=.verification/sqlite-pytest.xml")
    & (Join-Path $PSScriptRoot "Start-TestDatabase.ps1") -Backend $DatabaseBackend -Python $testPython -PostgresBin $PostgresBin -Port $PostgresPort
    Invoke-Checked -Executable $testPython -Arguments @("scripts/verify_phase1.py", "--database", "postgresql")
    Invoke-Checked -Executable $testPython -Arguments @("-m", "pytest", "-q", "--database", "postgresql", "--junitxml=.verification/postgresql-pytest.xml")
    Write-Output "Local verification passed. Known expected failures remain open findings; production is not accepted."
    if ($Push) {
        $remote = & git remote get-url origin
        if ($LASTEXITCODE -ne 0 -or $remote -ne "https://github.com/mignoncharly/kaemmerei.git") {
            throw "Refusing push: origin does not match the explicitly requested repository."
        }
        $changes = & git status --porcelain
        if ($LASTEXITCODE -ne 0 -or $changes) {
            throw "Commit reviewed source changes before using -Push. This script never stages unknown files."
        }
        Invoke-Checked -Executable "git" -Arguments @("push", "-u", "origin", "main")
        Write-Output "Push completed. Check https://github.com/mignoncharly/kaemmerei/actions for the actual Linux CI result."
    }
} finally {
    Pop-Location
}
