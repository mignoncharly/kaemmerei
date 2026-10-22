param(
    [string]$Python = 'C:\kämmerei\.venv\Scripts\python.exe',
    [ValidateSet('msedge','chrome','chromium')][string]$Channel = 'msedge',
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedSource
)
$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$run = Join-Path $project ('.verification\u023-browser-' + [guid]::NewGuid().ToString('N'))
$probe = [IO.DirectoryInfo]::new($run)
while ($null -ne $probe) {
    if ($probe.Exists -and (($probe.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { throw 'Linked verification output forbidden' }
    $probe = $probe.Parent
}
$null = New-Item -ItemType Directory -Path $run
$started = [DateTime]::UtcNow
$report = [ordered]@{
    format = 'ohvr-local-browser-verification-v2'
    source = $null
    status = 'not_run'
    exit_code = $null
    synthetic_only = $true
    check_count = 0
    result_sha256 = $null
    error_code = $null
}
Push-Location -LiteralPath $project
try {
    $source = (& git rev-parse HEAD).Trim()
    $report.source = $source
    if ($LASTEXITCODE -ne 0 -or ($ExpectedSource -and $source -cne $ExpectedSource)) {
        throw 'source_mismatch'
    }
    & $Python -c "from scripts.pilot_verification import source_identity; source_identity('$ExpectedSource')"
    if ($LASTEXITCODE -ne 0) { throw 'source_dirty' }
    # This invokes only the existing synthetic SQLite browser exercise.
    # No PostgreSQL setup, credentials, ACL, service, download or deployment.
    # Python captures child stdout/stderr directly, preserving warnings without
    # PowerShell 5 treating ordinary Python stderr as a terminating native error.
    & $Python -m scripts.run_pilot_verification --expected-source $source --selection browser --channel $Channel --output (Join-Path $run 'execution') *> (Join-Path $run 'private-wrapper.log')
    $report.exit_code = $LASTEXITCODE
    $result = Join-Path $run 'execution\browser\result.json'
    if ($report.exit_code -eq 0 -and (Test-Path -LiteralPath $result)) {
        $item = Get-Item -LiteralPath $result
        if ($item.LastWriteTimeUtc -lt $started) { throw 'stale_result' }
        $data = Get-Content -LiteralPath $result -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($data.source -cne $source -or $data.format -cne 'ohvr-browser-verification-v2' -or $data.status -cne 'passed' -or $data.synthetic_only -ne $true -or $data.checks.Count -lt 30) {
            throw 'unexpected_result'
        }
        if ((& git rev-parse HEAD).Trim() -cne $source) { throw 'source_changed' }
        & $Python -c "from scripts.pilot_verification import source_identity; source_identity('$ExpectedSource')"
        if ($LASTEXITCODE -ne 0) { throw 'source_dirty' }
        $report.status = 'passed'
        $report.check_count = $data.checks.Count
        $report.result_sha256 = (Get-FileHash -LiteralPath $result -Algorithm SHA256).Hash.ToLowerInvariant()
    } else {
        $report.status = 'failed_or_environment_blocked'
    }
} catch {
    # Do not emit exception text or private logs into the shareable report.
    $report.status = 'failed_or_environment_blocked'
    $report.error_code = 'local_execution_or_source_check_failed'
} finally {
    Pop-Location
    $json = $report | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText((Join-Path $run 'sanitized-report.json'), $json, [Text.UTF8Encoding]::new($false))
    Write-Output $json
}
if ($report.status -ne 'passed') { exit 2 }
