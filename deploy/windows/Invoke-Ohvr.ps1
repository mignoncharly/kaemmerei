[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('web','scan','purge','reconcile','integration-status','backup')][string]$Role,
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$Project,
    [Parameter(Mandatory)][string]$Config
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-LocalPath([string]$Value, [bool]$Directory) {
    if ($Value -notmatch '^[A-Za-z]:\\' -or $Value.Contains('"') -or $Value.Contains("`n") -or $Value.Contains("`r")) {
        throw 'An explicit local drive path is required.'
    }
    $item = Get-Item -LiteralPath $Value -Force
    if ([bool]$item.PSIsContainer -ne $Directory) { throw 'Unexpected configuration path type.' }
    $cursor = $item
    while ($null -ne $cursor) {
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Service paths must not traverse reparse points.'
        }
        if ($cursor -is [IO.DirectoryInfo]) { $cursor = $cursor.Parent }
        else { $cursor = $cursor.Directory }
    }
    return $item.FullName
}

try {
    $Python = Assert-LocalPath $Python $false
    $Project = Assert-LocalPath $Project $true
    $Config = Assert-LocalPath $Config $false
    $values = Get-Content -LiteralPath $Config -Raw -Encoding UTF8 | ConvertFrom-Json
    # A data-only file, not executable PowerShell. Separate ACLs and separate
    # passfiles are required per account; never dump the loaded object or env.
    $common = @('APP_ENV','DATABASE_URL','INTEGRATION_DATABASE_URL','ENFORCE_DATABASE_SECURITY',
        'ALLOWED_HOSTS','PGPASSFILE','DOCUMENT_STORAGE_DIR','CLAMAV_EXECUTABLE','CLAMAV_DATABASE_DIR',
        'SCANNER_TIMEOUT','SCANNER_MAX_AGE_HOURS','TRUSTED_PROXY_NETWORKS','REQUEST_MAX_BYTES',
        'REQUEST_TIMEOUT_SECONDS','REQUEST_CONCURRENCY','UPLOAD_CONCURRENCY','FORM_MAX_FIELDS',
        'FORM_MAX_FILES','FORM_FIELD_BYTES','DATABASE_POOL_SIZE','DATABASE_POOL_TIMEOUT',
        'DATABASE_STATEMENT_TIMEOUT_MS','DOCUMENT_STORAGE_QUOTA_BYTES','DOCUMENT_STORAGE_RESERVE_BYTES',
        'MANDATORY_REVIEW_RECIPIENTS','DMS_ALLOWED_HOSTS','REQUIRE_MFA','MFA_KEY_FILE','TEMP','TMP')
    $allowed = $common
    $backupNames = @('BACKUP_DATABASE','BACKUP_DIRECTORY','BACKUP_AGE_EXECUTABLE','BACKUP_AGE_SHA256',
        'BACKUP_RECIPIENTS_FILE','BACKUP_SIGNING_KEY_FILE','BACKUP_PG_DUMP')
    if ($Role -eq 'backup') { $allowed += $backupNames }
    if ($Role -eq 'purge') { $allowed += 'MAINTENANCE_DATABASE_URL' }
    elseif ($Role -ne 'web') { $allowed += 'MIGRATION_DATABASE_URL' }
    foreach ($name in ($common + $backupNames + @('MIGRATION_DATABASE_URL',
            'MAINTENANCE_DATABASE_URL','PGPASSWORD','PGSERVICE','PGSERVICEFILE'))) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    foreach ($property in $values.PSObject.Properties) {
        if ($property.Name -cnotin $allowed -or $property.Value -isnot [string]) {
            throw 'Unexpected service configuration key or value type.'
        }
        [Environment]::SetEnvironmentVariable($property.Name, $property.Value, 'Process')
    }
    if ($env:APP_ENV -cne 'production' -or $env:ENFORCE_DATABASE_SECURITY -cne '1') {
        throw 'Production configuration and restricted database roles are required.'
    }
    foreach ($name in @('PGPASSFILE','DOCUMENT_STORAGE_DIR','TEMP','TMP')) {
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        $null = Assert-LocalPath $value ($name -ne 'PGPASSFILE')
    }
    Set-Location -LiteralPath $Project
    if ($Role -eq 'web') {
        if ($env:TRUSTED_PROXY_NETWORKS -cne '127.0.0.1/32') {
            throw 'This template requires one IPv4 loopback TLS proxy.'
        }
        & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 `
            --no-proxy-headers --no-access-log --log-config deploy/windows/logging.json
    } elseif ($Role -eq 'backup') {
        # Encryption needs only public recipients, not the recovery identity or
        # MFA key contents. Signer is a separately protected operator file.
        foreach ($name in @('BACKUP_DIRECTORY','BACKUP_AGE_EXECUTABLE','BACKUP_RECIPIENTS_FILE',
                'BACKUP_SIGNING_KEY_FILE','BACKUP_PG_DUMP')) {
            $null = Assert-LocalPath ([Environment]::GetEnvironmentVariable($name, 'Process')) ($name -eq 'BACKUP_DIRECTORY')
        }
        & $Python -m app.cli backup-create --database $env:BACKUP_DATABASE `
            --directory $env:BACKUP_DIRECTORY --age $env:BACKUP_AGE_EXECUTABLE `
            --age-sha256 $env:BACKUP_AGE_SHA256 --recipients $env:BACKUP_RECIPIENTS_FILE `
            --signing-key $env:BACKUP_SIGNING_KEY_FILE --pg-dump $env:BACKUP_PG_DUMP
    } else {
        $commands = @{'scan'='scan-pending'; 'purge'='purge-sessions';
                      'reconcile'='document-reconcile'; 'integration-status'='integration-status'}
        & $Python -m app.cli $commands[$Role]
    }
    exit $LASTEXITCODE
} catch {
    # Exception text can contain secret-bearing JSON, authenticated URLs or paths.
    [Console]::Error.WriteLine('OPEN.HERZ operation failed; inspect protected configuration locally. No credentials were logged.')
    exit 1
}
