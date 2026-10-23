param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedSource,
    [string]$Python = 'python',
    [ValidateSet('msedge','chrome','chromium')][string]$Channel = 'msedge'
)
$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$verificationExit = 2
Push-Location -LiteralPath $project
try {
    # The Python coordinator captures native child output directly, avoiding
    # PowerShell 5 stderr handling changing child exit-code semantics.
    & $Python -m scripts.verify_integrated_browsers --expected-source $ExpectedSource --channel $Channel
    $verificationExit = $LASTEXITCODE
} catch {
    Write-Output 'FAILED: verification launcher could not start. No acceptance recorded.'
} finally {
    Pop-Location
}
exit $verificationExit
