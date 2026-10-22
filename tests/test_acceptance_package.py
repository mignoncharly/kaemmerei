"""Preparing evidence must not prefill participant outcomes or carry stale browser passes."""
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile
import pytest
from scripts.prepare_pilot_acceptance import build,validate_browser
from tests.support import scratch_directory


@pytest.mark.parametrize('fault',['none','hash','wrapper_count','parent_exit','source','browser_change','no_source_check'])
def test_browser_carry_forward_requires_all_three_artifacts_and_unchanged_inputs(monkeypatch,fault):
    with scratch_directory('ohvr-browser-provenance-') as directory:
        run=Path(directory);child=run/'execution/browser';child.mkdir(parents=True)
        browser={'format':'ohvr-browser-verification-v2','source':'a'*40,'synthetic_only':True,
                 'status':'passed','checks':['check_'+str(i) for i in range(31)]+['source_unchanged']}
        if fault=='no_source_check':browser['checks'].remove('source_unchanged')
        result=child/'result.json';result.write_text(json.dumps(browser),encoding='utf-8')
        digest=sha256(result.read_bytes()).hexdigest()
        parent={'format':'ohvr-revision-verification-v1','selection':'browser','source':'a'*40,
                'synthetic_only':True,'status':'VERIFIED','exit_code':0,'result_sha256':digest,
                'started_at':(datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat()}
        wrapper={'format':'ohvr-local-browser-verification-v2','source':'a'*40,'synthetic_only':True,
                 'status':'passed','exit_code':0,'check_count':32,'result_sha256':digest,'error_code':None}
        if fault=='wrapper_count':wrapper['check_count']=0
        if fault=='parent_exit':parent['exit_code']=1
        if fault=='source':wrapper['source']='b'*40
        (run/'sanitized-report.json').write_text(json.dumps(wrapper),encoding='utf-8')
        (run/'execution/sanitized-report.json').write_text(json.dumps(parent),encoding='utf-8')
        def git(command,**kwargs):return subprocess.CompletedProcess(command,1 if fault=='browser_change' and 'diff' in command else 0)
        monkeypatch.setattr(subprocess,'run',git)
        if fault=='none':
            report=validate_browser(run,'a'*40,digest,'b'*40)
            assert report['status']=='VERIFIED' and report['formal_participant_acceptance'] is False
        else:
            with pytest.raises(ValueError):validate_browser(run,'a'*40,'0'*64 if fault=='hash' else digest,'b'*40)


def test_prepared_package_is_auditable_and_keeps_twelve_cases_unexecuted():
    with scratch_directory('ohvr-acceptance-package-') as directory:
        output=Path(directory)/'package'
        report=build(output,'b'*40,{'status':'VERIFIED','source':'a'*40,'result_sha256':'c'*64})
        assert report['scenario_count']==12 and report['formal_acceptance_complete'] is False
        assert report['participant_results']['counts']['NOT_RUN']==12
        results=json.loads((output/'results.json').read_text(encoding='utf-8'))
        assert results['source']=='b'*40 and all(r['status']=='NOT_RUN' for r in results['results'])
        assert 'K?mmerei' not in (output/'SCENARIOS.md').read_text(encoding='utf-8')
        auth=json.loads((output/'authorization.json').read_text())
        assert auth['real_data_authorization']==auth['production_authorization']=='NOT_GRANTED'
        assert auth['automated_disposal_enabled'] is False
        with ZipFile(output/'acceptance.zip') as archive:
            assert archive.testzip() is None
            for name,digest in report['files'].items():assert sha256(archive.read(name)).hexdigest()==digest
        with pytest.raises(FileExistsError):build(output,'b'*40,{})
