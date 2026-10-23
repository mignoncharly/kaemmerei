# Read-only inventory to run ON an already authorized Windows host.
# No credentials, paths, computer/account names, service command lines or website files.
$ErrorActionPreference = 'Stop'
$report = [ordered]@{
    format = 'ohvr-read-only-windows-host-v1'
    observed_at = [DateTime]::UtcNow.ToString('o')
    product_tariff_verified = $false
    os = $null
    administrator_token = $null
    tools_found = [ordered]@{}
    service_counts = [ordered]@{}
    persistent_application_hosting_verified = $false
    vpn_firewall_tls_isolation_verified = $false
    changes_performed = $false
}
try {
    $os = Get-CimInstance -ClassName Win32_OperatingSystem
    $report.os = [ordered]@{ caption = $os.Caption; version = $os.Version; build = $os.BuildNumber }
} catch { $report.os = [ordered]@{ status = 'read_unavailable' } }
try {
    $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    $report.administrator_token = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
} catch { $report.administrator_token = $null }
foreach ($tool in @('python.exe','pg_dump.exe','pg_restore.exe','psql.exe','clamscan.exe','freshclam.exe','caddy.exe','age.exe')) {
    $report.tools_found[$tool] = [bool](Get-Command -Name $tool -CommandType Application -ErrorAction SilentlyContinue)
}
foreach ($kind in @('postgres','clam','caddy')) {
    try { $report.service_counts[$kind] = @(Get-Service -Name ('*'+$kind+'*') -ErrorAction SilentlyContinue).Count }
    catch { $report.service_counts[$kind] = $null }
}
$report | ConvertTo-Json -Depth 5
