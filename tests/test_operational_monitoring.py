"""Local failure evidence, read-only monitoring and atomic sequence publication."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import select, text

from app.monitoring import database_health, operational_health, newest_receipt
from app.operational_status import JOBS, tracked_job, job_health
from app.operations import publish_events
from app.models import SyncOutbox, SyncEvent
from tests.support import scratch_directory, login, create_contract
from tests.runtime_support import runtime_environment
from tests.test_backup_crypto import backup_keys


def test_job_failure_redaction_overlap_and_stale_evidence():
    with scratch_directory('ohvr-status-') as directory:
        root=Path(directory)
        with tracked_job(root,'scan-pending'):
            assert job_health(root)['scan-pending']=='missing_invalid_or_interrupted'
            with pytest.raises(OSError):
                with tracked_job(root,'scan-pending'):pass
        assert job_health(root)['scan-pending']=='ok'
        with pytest.raises(RuntimeError):
            with tracked_job(root,'scan-pending'):
                raise RuntimeError('secret-sentinel-do-not-log')
        assert 'secret-sentinel' not in (root/'scan-pending.json').read_text()
        assert job_health(root)['scan-pending']=='failed_or_stale'
        with tracked_job(root,'scan-pending'):pass
        assert job_health(root,clock=datetime.now(timezone.utc)+timedelta(days=2))['scan-pending']=='failed_or_stale'
        assert job_health(root,clock=datetime.now(timezone.utc)-timedelta(days=2))['scan-pending']=='failed_or_stale'
        (root/'scan-pending.json').write_text('x'*5000)
        assert job_health(root)['scan-pending']=='missing_invalid_or_interrupted'


def test_unknown_job_and_unprovisioned_status_directory_are_denied():
    with pytest.raises(ValueError):
        with tracked_job('relative','scan-pending'):pass
    with scratch_directory('ohvr-status-') as directory:
        with pytest.raises(ValueError):
            with tracked_job(directory,'disposal'):pass


def test_database_failure_missing_backup_and_disk_failure_are_unhealthy(environment):
    _, app=environment
    with scratch_directory('ohvr-monitor-') as directory:
        with (patch('app.monitoring.database_health',side_effect=RuntimeError('secret-url')),
              patch('app.monitoring.shutil.disk_usage',side_effect=OSError('private-path'))):
            result=operational_health(app.state.engine,Path(directory),Path(directory),Path(directory)/'missing',Path(directory)/'missing')
        assert not result['healthy'] and not result['checks']['database'] and not result['checks']['backup']
        assert not result['checks']['storage_capacity'] and not result['external_delivery']
        assert 'secret-url' not in json.dumps(result) and 'private-path' not in json.dumps(result)


def test_signed_backup_age_and_tamper_drive_local_health(environment,backup_keys):
    from app.backup_crypto import encrypt_stream, file_digest, signed_receipt
    keys=backup_keys; _, app=environment
    status=keys.root/'status';status.mkdir()
    for job in JOBS:
        with tracked_job(status,job):pass
    artifact=keys.root/('bundle-'+'1'*32+'.tar.age')
    encrypt_stream(keys.executable,keys.recipients,artifact,lambda stream:stream.write(b'synthetic'),seconds=15)
    digest,size=file_digest(artifact)
    clock=datetime.now(timezone.utc)
    metadata=dict(format='ohvr-backup-v1',created_at=clock.isoformat(),finished_at=clock.isoformat(),
        schema_head='0023_human_mfa',ciphertext_file=artifact.name,ciphertext_sha256=digest,ciphertext_bytes=size,file_count=0)
    receipt=keys.root/'receipt.json';receipt.write_text(json.dumps(signed_receipt(metadata,keys.signer)))
    def check(**kwargs):
        return operational_health(app.state.engine,keys.root,status,receipt,keys.verifier,**kwargs)
    assert check()['healthy']
    assert not check(clock=clock+timedelta(hours=25))['checks']['backup']
    assert not check(clock=clock-timedelta(seconds=1))['checks']['backup']
    artifact.write_bytes(artifact.read_bytes()+b'corrupt')
    assert not check()['checks']['backup']


def test_backup_candidate_selection_never_accepts_missing_inventory():
    with scratch_directory('ohvr-monitor-') as directory:
        with pytest.raises(ValueError):newest_receipt(directory)


@pytest.mark.postgresql
def test_publication_bounded_idempotent_and_restricted_role_denied(request):
    if request.config.getoption('--database')!='postgresql':pytest.skip('Actual PostgreSQL owner/roles required')
    with runtime_environment() as runtime:
        assert login(runtime.client,'admin').status_code==303
        for i in range(3):create_contract(runtime.client,designation=f'Synthetic publication {i}')
        before=database_health(runtime.owner.state.engine)['unpublished_events']
        assert before>=3
        with pytest.raises(PermissionError):publish_events(runtime.app.state.engine)
        assert publish_events(runtime.owner.state.engine,limit=1)['published']==1
        assert database_health(runtime.owner.state.engine)['unpublished_events']==before-1
        assert publish_events(runtime.owner.state.engine)['published']==before-1
        assert publish_events(runtime.owner.state.engine)['published']==0
        with runtime.owner.state.engine.connect() as connection:
            assert connection.scalar(text('SELECT count(*) FROM sync_events'))==before
            assert connection.scalar(text('SELECT count(*) FROM sync_outbox'))==before
            assert connection.scalar(text('SELECT count(DISTINCT seq) FROM sync_events'))==before
        for engine in (runtime.app.state.engine,runtime.app.state.integration_engine):
            with pytest.raises(PermissionError):database_health(engine)


def test_http_surfaces_explicit_pending_business_rules(environment):
    client, _=environment
    assert login(client,'admin').status_code==303
    response=client.get('/reports')
    assert 'fachlich noch nicht bestätigt' in response.text
    assert 'finance=pending' in response.headers['X-OHVR-Business-Rules']
