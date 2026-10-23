"""Review preparation is local; incomplete gates and stale engines cannot become passes."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile
import pytest
import yaml
from scripts import review_candidate
from scripts.scanner_readiness import inventory,supported_engine
from tests.support import scratch_directory


@pytest.mark.parametrize('version,valid',[
    ('1.4.6',True),('1.4.7',True),('1.5.4',True),('1.0.9',False),('1.4.3',False),('1.5.3',False),('2.0.0',False)])
def test_maintained_engine_policy_does_not_confuse_signature_access_with_patch_support(version,valid):
    policy=json.loads(Path('docs/pilot/scanner-engine-baseline-v1.json').read_text())
    raw='ClamAV '+version+'/123/Thu Oct 22 08:00:00 2026'
    if valid:assert supported_engine(raw,policy,date(2026,10,22))==version
    else:
        with pytest.raises(ValueError):supported_engine(raw,policy,date(2026,10,22))


def test_expired_policy_and_unrecognized_version_cannot_pass():
    policy=json.loads(Path('docs/pilot/scanner-engine-baseline-v1.json').read_text())
    for raw,day in [('ClamAV 1.4.6/123/Thu Oct 22 08:00:00 2026',date(2026,11,23)),('private-path SECRET',date(2026,10,22))]:
        with pytest.raises(ValueError):supported_engine(raw,policy,day)


def test_unconfigured_scanner_inventory_never_claims_real_verification(monkeypatch):
    monkeypatch.delenv('CLAMAV_EXECUTABLE',raising=False);monkeypatch.delenv('CLAMAV_DATABASE_DIR',raising=False)
    report=inventory({})
    assert report['status']=='EXTERNALLY_BLOCKED' and not report['real_engine_integration_verified']
    assert not report['official_signature_authenticity_verified'] and not report['installation_changed']


def test_ci_matrix_requires_all_ten_exact_source_executions():
    path=Path('.github/workflows/phase1-verification.yml');report=review_candidate.ci_matrix(path)
    assert len(report['executions'])==10 and all(row['status']=='NOT_RUN' for row in report['executions'])
    assert not report['hosted_execution_authorized'] and not report['hosted_success_claimed']
    workflow=yaml.safe_load(path.read_text())
    assert any('scripts.scanner_readiness' in step.get('run','') for step in workflow['jobs']['document-scanner']['steps'])
    with scratch_directory('ohvr-ci-matrix-') as directory:
        bad=Path(directory)/'workflow.yml';workflow['jobs'].pop('document-scanner')
        bad.write_text(yaml.safe_dump(workflow))
        with pytest.raises(ValueError):review_candidate.ci_matrix(bad)


def test_archive_validation_detects_changed_retained_evidence(monkeypatch):
    with scratch_directory('ohvr-retained-package-') as directory:
        path=Path(directory)/'acceptance.zip'
        payloads={'results.json':json.dumps({'source':review_candidate.PACKAGE_SOURCE,'results':[{'status':'NOT_RUN'}]*12}),
                  'browser-evidence.json':json.dumps({'source':review_candidate.BROWSER_SOURCE,'result_sha256':review_candidate.BROWSER_HASH})}
        manifest={'source':review_candidate.PACKAGE_SOURCE,'files':{n:sha256(v.encode()).hexdigest() for n,v in payloads.items()}}
        with ZipFile(path,'w') as archive:
            for name,value in payloads.items():archive.writestr(name,value)
            archive.writestr('manifest.json',json.dumps(manifest))
        monkeypatch.setattr(review_candidate,'PACKAGE_HASH',sha256(path.read_bytes()).hexdigest())
        assert review_candidate.verify_package(path)['participant_cases_executed']==0
        with path.open('ab') as handle:handle.write(b'TAMPERED')
        with pytest.raises(ValueError,match='hash mismatch'):review_candidate.verify_package(path)
