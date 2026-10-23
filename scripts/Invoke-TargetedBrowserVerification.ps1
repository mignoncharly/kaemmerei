param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedSource,
    [Parameter(Mandatory=$true)][ValidateSet('toolbar','excel')][string]$Suite,
    [string]$Python = 'python',
    [ValidateSet('msedge','chrome','chromium')][string]$Channel = 'msedge'
)
$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$verificationExit = 2
Push-Location -LiteralPath $project
try {
    & $Python -m scripts.verify_integrated_browsers --expected-source $ExpectedSource --channel $Channel --suite $Suite
    $verificationExit = $LASTEXITCODE
} catch {
    Write-Output 'FAILED: targeted verification could not start. No acceptance recorded.'
} finally {
    Pop-Location
}
exit $verificationExit
