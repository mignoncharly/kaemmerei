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
    failing_stage = $null
    diagnostic_summary = $null
    child_exit_code = $null
    failed_check = $null
}
Push-Location -LiteralPath $project
$stage = 'source_validation'
try {
    $source = (& git rev-parse HEAD).Trim()
    $report.source = $source
    if ($LASTEXITCODE -ne 0 -or ($ExpectedSource -and $source -cne $ExpectedSource)) {
        throw 'source_mismatch'
    }
    $stage = 'dependencies'
    & $Python -c "from scripts.pilot_verification import source_identity; source_identity('$ExpectedSource')" *> (Join-Path $run 'private-source.log')
    $stage = 'source_validation'
    if ($LASTEXITCODE -ne 0) { throw 'source_dirty' }
    # This invokes only the existing synthetic SQLite browser exercise.
    # No PostgreSQL setup, credentials, ACL, service, download or deployment.
    # Python captures child stdout/stderr directly, preserving warnings without
    # PowerShell 5 treating ordinary Python stderr as a terminating native error.
    $stage = 'child_execution'
    & $Python -m scripts.run_pilot_verification --expected-source $source --selection browser --channel $Channel --output (Join-Path $run 'execution') *> (Join-Path $run 'private-wrapper.log')
    $report.exit_code = $LASTEXITCODE
    $stage = 'result_validation'
    $result = Join-Path $run 'execution\browser\result.json'
    if ($report.exit_code -eq 0 -and (Test-Path -LiteralPath $result)) {
        $item = Get-Item -LiteralPath $result
        if ($item.LastWriteTimeUtc -lt $started) { throw 'stale_result' }
        $data = Get-Content -LiteralPath $result -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($data.source -cne $source -or $data.format -cne 'ohvr-browser-verification-v2' -or $data.status -cne 'passed' -or $data.synthetic_only -ne $true -or $data.checks.Count -lt 30) {
            throw 'unexpected_result'
        }
        if ((& git rev-parse HEAD).Trim() -cne $source) { throw 'source_changed' }
        $stage = 'source_validation'
        & $Python -c "from scripts.pilot_verification import source_identity; source_identity('$ExpectedSource')" *> (Join-Path $run 'private-source-final.log')
        if ($LASTEXITCODE -ne 0) { throw 'source_dirty' }
        $report.status = 'passed'
        $report.check_count = $data.checks.Count
        $report.result_sha256 = (Get-FileHash -LiteralPath $result -Algorithm SHA256).Hash.ToLowerInvariant()
    } else {
        $report.status = 'failed_or_environment_blocked'
        $report.error_code = 'browser_child_failed_without_result'
        $report.failing_stage = 'child_execution'
        $report.diagnostic_summary = 'The browser process did not produce a valid passing result. Inspect the private local logs.'
        $childPath = Join-Path $run 'execution\sanitized-report.json'
        if (Test-Path -LiteralPath $childPath) {
            $child = Get-Content -LiteralPath $childPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($child.source -cne $source -or $child.format -cne 'ohvr-revision-verification-v1' -or $child.selection -cne 'browser' -or $child.synthetic_only -ne $true) { throw 'unexpected_child_report' }
            $codes = @('browser_assertion_failed','browser_dependency_missing','automation_driver_permission_denied','browser_permission_denied','browser_launch_failed','browser_timeout','source_validation_failed','browser_execution_failed','browser_result_invalid','browser_child_failed_without_result','verification_launcher_failed')
            $stages = @('dependencies','synthetic_fixture','automation_driver','browser_launch','browser_scenarios','document_upload','document_download','review_request','archive','mfa','source_validation','child_execution','result_validation')
            if ($codes -ccontains $child.error_code -and $stages -ccontains $child.failing_stage) {
                $report.error_code = $child.error_code
                $report.failing_stage = $child.failing_stage
                $report.diagnostic_summary = 'The synthetic browser exercise failed at the reported stage; error_code identifies the failure category.'
                if ($child.check_count -is [int] -and $child.check_count -ge 0) { $report.check_count = $child.check_count }
                if ($child.exit_code -is [int]) { $report.child_exit_code = $child.exit_code }
                if ($child.failed_check -cmatch '^[a-z][a-z0-9_]{0,99}$') { $report.failed_check = $child.failed_check }
            }
        }
    }
} catch {
    # Do not emit exception text or private logs into the shareable report.
    $report.status = 'failed_or_environment_blocked'
    $report.error_code = 'verification_launcher_failed'
    if ($stage -eq 'source_validation') { $report.error_code = 'source_validation_failed' }
    if ($stage -eq 'dependencies') { $report.error_code = 'browser_dependency_missing' }
    if ($stage -eq 'result_validation') { $report.error_code = 'browser_result_invalid' }
    $report.failing_stage = $stage
    $report.diagnostic_summary = 'The local verification launcher could not complete the reported stage; inspect private logs locally.'
} finally {
    Pop-Location
    $json = $report | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText((Join-Path $run 'sanitized-report.json'), $json, [Text.UTF8Encoding]::new($false))
    Write-Output $json
}
if ($report.status -ne 'passed') { exit 2 }
