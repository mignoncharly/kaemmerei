"""Review-only Windows bundles; no service/task registration or network access."""
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest

from scripts.render_windows_tasks import NS, task_xml

BASE = dict(python=r'C:\ohvr\venv\Scripts\python.exe', project=r'C:\ohvr\release',
            config=r'C:\ohvr-private\web.json', account=r'MUNICIPAL\ohvr-web')


@pytest.mark.parametrize('role', ['web','scan','purge','reconcile','integration-status','backup','events','monitor'])
def test_windows_task_is_disabled_restricted_and_has_no_inline_secrets(role):
    raw = task_xml(role=role, **BASE)
    root = ET.fromstring(raw)
    def value(path):return root.find(path, {'t':NS}).text
    assert value('t:Settings/t:Enabled') == 'false'
    assert value('t:Settings/t:MultipleInstancesPolicy') == 'IgnoreNew'
    assert value('t:Principals/t:Principal/t:RunLevel') == 'LeastPrivilege'
    assert value('t:Principals/t:Principal/t:UserId') == BASE['account']
    assert '-WindowStyle Hidden' in value('t:Actions/t:Exec/t:Arguments')
    assert '-ExecutionPolicy' not in value('t:Actions/t:Exec/t:Arguments')
    assert b'postgresql' not in raw and b'PGPASSWORD' not in raw
    assert value('t:Settings/t:ExecutionTimeLimit') == ('PT0S' if role=='web' else 'PT70M' if role=='backup' else 'PT10M')
    if role=='backup':
        assert value('t:Triggers/t:CalendarTrigger/t:Repetition/t:Interval')=='PT12H'


@pytest.mark.parametrize('path', [r'\\server\share\app',r'C:\ok\..\other',
                                      'C:\\bad" -Command malicious', 'relative'])
def test_windows_task_rejects_unsafe_path_arguments(path):
    with pytest.raises(ValueError):
        task_xml(role='web', **{**BASE,'project':path})


def test_windows_logging_enables_only_redacted_request_stream():
    config=json.loads(Path('deploy/windows/logging.json').read_text())
    assert config['loggers']['ohvr.requests']['level']=='INFO'
    assert not config['loggers']['uvicorn.access']['handlers']
    assert config['handlers']['requests']['maxBytes']==10485760
    assert config['handlers']['requests']['backupCount']==7


@pytest.mark.skipif(os.name!='nt', reason='Actual Windows PowerShell parser required')
@pytest.mark.parametrize('script',['deploy/windows/Invoke-Ohvr.ps1','scripts/Invoke-PilotBrowserVerification.ps1','scripts/Get-PilotHostInventory.ps1'])
def test_windows_launcher_has_valid_actual_powershell_syntax(script):
    command = "$tokens=$null; $errors=$null; [void][System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PWD '"+script+"'),[ref]$tokens,[ref]$errors); if($errors.Count){exit 1}"
    completed=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
    assert completed.returncode==0
