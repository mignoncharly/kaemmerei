param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedSource,
    [string]$Python = 'python',
    [ValidateRange(1,48)][int]$WaitHours = 24
)
$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$acceptanceExit = 2
Push-Location -LiteralPath $project
try {
    & $Python -m scripts.github_release_acceptance --expected-source $ExpectedSource --wait-hours $WaitHours
    $acceptanceExit = $LASTEXITCODE
} catch {
    Write-Output 'BLOCKED: release launcher could not complete. No release acceptance recorded.'
} finally {
    Pop-Location
}
exit $acceptanceExit
