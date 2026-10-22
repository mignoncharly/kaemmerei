# Authorized local dependency provisioning, followed by read-only remote discovery.
# Never reads credentials in PowerShell, changes ACLs, accepts unknown host keys,
# changes proxy/index policy, or alters the STRATO server.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path (Split-Path -Parent $repo) '.venv\Scripts\python.exe'
$outputDirectory = Join-Path $repo ('.verification\strato-readonly-' + [guid]::NewGuid().ToString('N'))
try {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        Write-Output '{"status":"BLOCKED","error_code":"SPECIFIED_VENV_UNAVAILABLE"}'
        exit 2
    }
    # The reviewed upstream/PyPI version is pinned; no security downgrade or source build.
    $version = & $python -c "import importlib.metadata as m; import importlib.util as u; print(m.version('paramiko') if u.find_spec('paramiko') else 'MISSING')"
    $installed = ($LASTEXITCODE -eq 0 -and "$version".Trim() -eq '5.1.0')
    if (-not $installed) {
        # Suppress raw pip diagnostics, which may contain private configured index URLs.
        # Keep existing proxy/security policy. If blocked, report and stop.
        $installCode = @'
import subprocess, sys
r = subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input', '--no-cache-dir', '--only-binary=:all:', '--index-url', 'https://pypi.org/simple', '--retries', '0', '--timeout', '15', 'paramiko==5.1.0'], capture_output=True)
sys.exit(r.returncode)
'@
        $installCode | & $python -
        $pipExit = $LASTEXITCODE
        if ($pipExit -ne 0) {
            Write-Output '{"status":"BLOCKED","error_code":"PARAMIKO_INSTALL_UNAVAILABLE","failing_stage":"local_dependency_install"}'
            exit 2
        }
    }
    & $python (Join-Path $PSScriptRoot 'assess_strato_readonly.py') --output (Join-Path $outputDirectory 'sanitized-report.json')
    exit $LASTEXITCODE
} catch {
    # Never echo exception messages, credential values or diagnostic process output.
    Write-Output '{"status":"BLOCKED","error_code":"LOCAL_LAUNCHER_FAILED","failing_stage":"local_launcher"}'
    exit 2
}
