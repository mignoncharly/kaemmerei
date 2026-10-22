"""Browser failures must retain partial evidence without leaking private exceptions."""
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from scripts.browser_diagnostics import browser_result,failure
from tests.support import scratch_directory


@pytest.mark.parametrize('error,stage,code',[
    (AssertionError('private URL https://private.invalid/?token=SECRET'),'document_upload','browser_assertion_failed'),
    (ModuleNotFoundError('SECRET'),'dependencies','browser_dependency_missing'),
    (PermissionError('SECRET'),'automation_driver','automation_driver_permission_denied'),
    (PermissionError('SECRET'),'browser_launch','browser_permission_denied'),
    (RuntimeError('SECRET'),'browser_launch','browser_launch_failed'),
    (TimeoutError('SECRET'),'mfa','browser_timeout'),
    (ValueError('SECRET'),'source_validation','source_validation_failed'),
])
def test_failure_classification_does_not_serialize_exception_text(error,stage,code):
    report=failure(error,stage,'pilot_clean_document_listed')
    assert report['error_code']==code and report['failing_stage']==stage
    assert 'SECRET' not in json.dumps(report) and 'https://' not in json.dumps(report)


def test_browser_main_preserves_partial_checks_and_structured_assertion(monkeypatch,capsys):
    from scripts import verify_phase8_browser as browser
    from scripts import pilot_verification
    with scratch_directory('ohvr-browser-report-') as directory:
        output=Path(directory)/'browser'
        monkeypatch.setattr(sys,'argv',['browser','--output',str(output)])
        monkeypatch.setattr(pilot_verification,'source_identity',lambda *args:'a'*40)
        def execute(args,path,results):
            results.update(stage='document_upload',checks=['fixture_edit','server_started'],failed_check='pilot_clean_document_listed')
            raise AssertionError('SECRET authenticated URL')
        monkeypatch.setattr(browser,'execute',execute)
        with pytest.raises(SystemExit) as exited:browser.main()
        assert exited.value.code==1
        report=json.loads((output/'result.json').read_text())
        assert report['status']=='failed' and len(report['checks'])==2
        assert report['failed_check']=='pilot_clean_document_listed'
        assert report['failing_stage']=='document_upload' and report['error_code']=='browser_assertion_failed'
        assert 'SECRET' not in capsys.readouterr().out


@pytest.mark.parametrize('fault',['none','missing','malformed','stale','wrong_source','few_checks','duplicate','nonzero_exit','failure','unsafe_summary'])
def test_browser_result_requires_fresh_complete_source_bound_success(fault):
    with scratch_directory('ohvr-browser-validate-') as directory:
        path=Path(directory)/'result.json';started=datetime.now(timezone.utc)
        data={'source':'a'*40,'format':'ohvr-browser-verification-v2','synthetic_only':True,
              'status':'passed','checks':['case_'+str(i) for i in range(30)]+['source_unchanged']}
        code=0
        if fault=='wrong_source':data['source']='b'*40
        if fault=='few_checks':data['checks']=['source_unchanged']
        if fault=='duplicate':data['checks']=['source_unchanged']*31
        if fault=='nonzero_exit':code=1
        if fault in ('failure','unsafe_summary'):
            code=1;data.update(status='failed',error_code='browser_assertion_failed',failing_stage='document_upload',
                               diagnostic_summary='SECRET https://private.invalid',failed_check='pilot_clean_document_listed')
        if fault!='missing':path.write_text('malformed' if fault=='malformed' else json.dumps(data),encoding='utf-8')
        if fault not in ('missing','stale'):
            fresh=(started+timedelta(seconds=1)).timestamp();os.utime(path,(fresh,fresh))
        if fault=='stale':
            old=(started-timedelta(hours=1)).timestamp();os.utime(path,(old,old))
        passed,report=browser_result(path,'a'*40,started.isoformat(),code)
        assert passed==(fault=='none')
        assert 'SECRET' not in json.dumps(report) and 'https://' not in json.dumps(report)
        if fault in ('failure','unsafe_summary'):
            assert report['check_count']==31 and report['failing_stage']=='document_upload'
        elif fault!='none':assert report['error_code'] in ('browser_result_invalid','browser_child_failed_without_result')


def test_department_document_upload_is_available_and_filename_has_decorative_prefix():
    from sqlalchemy import select
    from app.models import ContractDocument
    from tests.support import environment_context,login,create_contract,workflow_payload,csrf_from
    with environment_context() as (client,app):
        login(client,'kultur');cid=create_contract(client)
        path=f'/contracts/{cid}/documents'
        response=client.post(path,data=workflow_payload(client,path,{'csrf_token':csrf_from(client.get('/').text)}),
            files={'documents':('synthetic.txt',b'Synthetic contract attachment','text/plain')},follow_redirects=False)
        assert response.status_code==303
        with app.state.session_factory() as db:
            document=db.scalar(select(ContractDocument).where(ContractDocument.contract_id==cid))
            assert document.state=='available'
            download=client.get(f'/contracts/{cid}/documents/{document.id}?download=1')
            assert download.status_code==200 and download.content==b'Synthetic contract attachment'
        html=client.get(f'/contracts/{cid}').text
        label=re.search(r'<div class="document-meta"><strong>(.*?)</strong>',html,re.S)[1].strip()
        assert label!='synthetic.txt' and re.search(r'(?:^|\s)synthetic\.txt$',label)


@pytest.mark.skipif(os.name!='nt',reason='Actual Windows PowerShell required')
@pytest.mark.parametrize('child_report',['structured_failure','missing_report','malformed_report'])
def test_actual_powershell_wrapper_propagates_or_classifies_child_failure(child_report):
    with scratch_directory('ohvr-wrapper-test-') as directory:
        stub=Path(directory)/'synthetic-python.ps1'
        # Test double only: no browser/database/services. Exercise the real launcher.
        stub.write_text("""if ($args[0] -eq '-c') { exit 0 }
$target = $args[$args.Count - 1]
$null = New-Item -ItemType Directory -Path $target
$report = @{format='ohvr-revision-verification-v1';source=$args[3];selection='browser';synthetic_only=$true;error_code='browser_assertion_failed';failing_stage='document_upload';check_count=24;exit_code=1;failed_check='pilot_clean_document_listed'}
"""+ ("$report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $target 'sanitized-report.json') -Encoding UTF8\n" if child_report=='structured_failure' else "'invalid' | Set-Content -LiteralPath (Join-Path $target 'sanitized-report.json') -Encoding UTF8\n" if child_report=='malformed_report' else '')+"exit 2\n",encoding='utf-8-sig')
        source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        done=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',
            'scripts/Invoke-PilotBrowserVerification.ps1','-Python',str(stub),'-ExpectedSource',source],
            capture_output=True,text=True,timeout=30)
        assert done.returncode==2
        report=json.loads(done.stdout)
        assert report['status']=='failed_or_environment_blocked' and report['error_code']
        if child_report=='structured_failure':
            assert report['check_count']==24 and report['child_exit_code']==1
            assert report['error_code']=='browser_assertion_failed' and report['failing_stage']=='document_upload'
        elif child_report=='missing_report':assert report['error_code']=='browser_child_failed_without_result'
        else:assert report['error_code']=='browser_result_invalid'


@pytest.mark.parametrize('scenario',['source_failure','process_permission','zero_without_result','child_assertion'])
def test_revision_runner_never_accepts_unverified_browser_child(monkeypatch,capsys,scenario):
    from scripts import run_pilot_verification as runner
    with scratch_directory('ohvr-runner-report-') as directory:
        output=Path(directory)/'execution'
        monkeypatch.setattr(sys,'argv',['runner','--expected-source','a'*40,'--selection','browser','--output',str(output)])
        def source(*args):
            if scenario=='source_failure':raise ValueError('SECRET source details')
            return 'a'*40
        monkeypatch.setattr(runner,'source_identity',source)
        def child(command,**kwargs):
            if scenario=='process_permission':raise PermissionError('SECRET process path')
            if scenario=='child_assertion':
                path=output/'browser';path.mkdir()
                data={'format':'ohvr-browser-verification-v2','source':'a'*40,'status':'failed','synthetic_only':True,
                      'checks':['fixture_edit'],**failure(AssertionError('SECRET'),'document_upload','pilot_clean_document_listed')}
                (path/'result.json').write_text(json.dumps(data),encoding='utf-8')
            return subprocess.CompletedProcess(command,1 if scenario=='child_assertion' else 0)
        monkeypatch.setattr(runner.subprocess,'run',child)
        with pytest.raises(SystemExit) as exited:runner.main()
        assert exited.value.code==2
        report=json.loads((output/'sanitized-report.json').read_text())
        assert report['status']=='IMPLEMENTED BUT UNVERIFIED' and report['error_code']
        assert report['executed']==(scenario not in ('source_failure','process_permission'))
        assert 'SECRET' not in capsys.readouterr().out
        if scenario=='child_assertion':assert report['check_count']==1 and report['failed_check']=='pilot_clean_document_listed'
