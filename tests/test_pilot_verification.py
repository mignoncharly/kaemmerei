"""Evidence must reject stale sources, omissions and invented acceptance passes."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import subprocess
import pytest
from app.config import Settings
from app.documents import ClamAVScanner
from app.server_security import validate_client_version
from scripts.pilot_verification import review_skips,validate_acceptance


@pytest.mark.parametrize('tool',['pg_dump','pg_restore','psql'])
def test_native_client_identity_and_complete_version_output(tool):
    assert validate_client_version((tool+' (PostgreSQL) 18.6\n').encode(),tool)==180006
    for suffix in ('beta1','\nmalformed','\npg_dump (PostgreSQL) 18.3'):
        with pytest.raises(ValueError):validate_client_version((tool+' (PostgreSQL) 18.6'+suffix).encode(),tool)


@pytest.mark.parametrize('exit_code,outcome',[(0,'clean'),(1,'infected'),(2,'error'),(-1,'error')])
def test_scanner_exit_mapping_and_explicit_official_limit_flags(monkeypatch,exit_code,outcome):
    calls=[]
    stamp=datetime.now(timezone.utc).strftime('%a %b %d %H:%M:%S %Y')
    def run(command,**kwargs):
        calls.append((command,kwargs))
        return subprocess.CompletedProcess(command,0 if len(calls)==1 else exit_code,
            stdout=('ClamAV 1.4.3/123/'+stamp).encode())
    monkeypatch.setattr(subprocess,'run',run)
    result=ClamAVScanner(Settings(clamav_executable=Path('synthetic'))).scan(b'Synthetic input')
    assert result.outcome==outcome and len(calls)==2
    command,options=calls[1]
    assert {'--official-db-only=yes','--heuristic-alerts=yes','--alert-encrypted=yes',
            '--alert-exceeds-max=yes','--alert-macros=yes','--max-filesize=30M','--max-scansize=100M','-'}<=set(command)
    assert options['input']==b'Synthetic input' and options['timeout']>0
    assert not any(v.startswith(('--remove','--move','--copy')) for v in command)


@pytest.mark.parametrize('fault',['timeout','missing','future','oversized_version'])
def test_scanner_failures_never_return_clean(monkeypatch,fault):
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        if fault=='missing':raise OSError('private scanner path')
        if fault=='timeout':raise subprocess.TimeoutExpired(command,1)
        stamp=(datetime.now(timezone.utc)+timedelta(days=1)).strftime('%a %b %d %H:%M:%S %Y')
        return subprocess.CompletedProcess(command,0,stdout=('ClamAV 1.4.3/123/'+stamp if fault=='future' else 'x'*10000).encode())
    monkeypatch.setattr(subprocess,'run',run)
    assert ClamAVScanner(Settings(clamav_executable=Path('synthetic'))).scan(b'Synthetic').outcome!='clean'
    assert len(calls)==1


def test_missing_or_unexecuted_counterpart_cannot_close_a_skip():
    from tests.support import scratch_directory
    with scratch_directory('ohvr-skip-review-') as directory:
        _assert_skip_review(Path(directory))


def _assert_skip_review(tmp_path):
    pg=tmp_path/'pg.xml';sq=tmp_path/'sq.xml'
    pg.write_text('<testsuite><testcase classname="c" name="rls"/><testcase classname="c" name="av"><skipped message="missing scanner"/></testcase></testsuite>')
    sq.write_text('<testsuite><testcase classname="c" name="rls"><skipped message="PostgreSQL only"/></testcase><testcase classname="c" name="av"><skipped message="missing scanner"/></testcase></testsuite>')
    rows=review_skips(pg,sq)['skips']
    assert sum(r['classification']=='EXPECTED_BACKEND_SKIP_COVERED_BY_POSTGRESQL' for r in rows)==1
    assert sum(r['classification']=='MISSING_LOCAL_ENVIRONMENT_COVERAGE' for r in rows)==2


def test_acceptance_requires_exact_source_complete_cases_and_observed_evidence():
    packet={'scenarios':[{'id':'PILOT-001'}]}
    results={'source':'a'*40,'synthetic_only':True,'results':[{'id':'PILOT-001','status':'NOT_RUN'}]}
    assert not validate_acceptance(packet,results,'a'*40)['all_scenarios_passed']
    with pytest.raises(ValueError):validate_acceptance(packet,results,'b'*40)
    row=results['results'][0];row['status']='PASSED'
    with pytest.raises(ValueError):validate_acceptance(packet,results,'a'*40)

    row.update(participant_role='Responsible Kämmerei representative',observed_at='2026-10-22T09:00:00+02:00',actual='Observed expected behavior',evidence_reference='local case reference')
    report=validate_acceptance(packet,results,'a'*40)
    assert report['all_scenarios_passed'] and not report['formal_authorization_granted']
    results['results'].append(dict(row))
    with pytest.raises(ValueError):validate_acceptance(packet,results,'a'*40)


def test_report_path_cannot_escape_verification_or_overwrite():
    from scripts.pilot_verification import ROOT,write_report
    from tests.support import scratch_directory
    with pytest.raises(ValueError):write_report(ROOT/'.verification/../unsafe-pilot-report.json',{})
    with scratch_directory('ohvr-report-') as directory:
        path=Path(directory)/'report.json';write_report(path,{'status':'NOT_RUN'})
        with pytest.raises(FileExistsError):write_report(path,{'status':'PASSED'})
        assert 'NOT_RUN' in path.read_text()


@pytest.mark.parametrize('restore_major,passed',[(18,True),(17,False)])
def test_native_attestation_requires_matching_patched_tool_family(monkeypatch,restore_major,passed):
    import os
    import psycopg
    from scripts.pilot_verification import native_report
    from tests.support import scratch_directory
    class Result:
        def __init__(self,value):self.value=value
        def fetchone(self):return [self.value]
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,query):return Result('180006' if 'version_num' in query else 'on')
    monkeypatch.setattr(psycopg,'connect',lambda *a,**k:Connection())
    monkeypatch.setenv('TEST_POSTGRES_ADMIN_URL','postgresql+psycopg://synthetic@127.0.0.1:55432/postgres')
    def version(command,**kwargs):
        tool=Path(command[0]).stem
        value=('17.11' if restore_major==17 else '18.6') if tool=='pg_restore' else '18.6'
        return subprocess.CompletedProcess(command,0,stdout=(tool+' (PostgreSQL) '+value+'\n').encode())
    monkeypatch.setattr(subprocess,'run',version)
    with scratch_directory('ohvr-native-inventory-') as directory:
        for name in ('pg_dump','pg_restore','psql'):
            (Path(directory)/(name+('.exe' if os.name=='nt' else ''))).write_bytes(b'Synthetic fixture, never executed')
        report=native_report(Path(directory),True)
    assert report['baseline_passed'] is passed and report['client_server_major_match'] is passed
    assert not report['r43_closed'] and not report['installation_changed']


def test_extracted_artifact_cannot_claim_parent_repository_revision(monkeypatch):
    import scripts.pilot_verification as evidence
    from tests.support import scratch_directory
    with scratch_directory('ohvr-parent-git-') as directory:
        monkeypatch.setattr(evidence,'ROOT',Path(directory))
        with pytest.raises(ValueError,match='actual repository root'):evidence.source_identity()
