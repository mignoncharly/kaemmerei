"""Durable retries use only marked disposable databases and synthetic files."""
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select, text

from app.config import Settings
from app.models import Contract, ContractDocument, DocumentJob, User, now_utc
from app.operations import SCAN_LOCK, scan_batch
from tests.scanner_support import CleanScanner
from tests.test_phase5 import documents, upload, ResultScanner


def test_production_always_queues_scans():
    assert Settings(environment='production').queued_document_scans
    assert not Settings().queued_document_scans
    assert Settings(defer_document_scans=True).queued_document_scans


def test_deferred_upload_never_scans_in_request_and_denies_download(documents):
    client, app, owner = documents
    app.state.config = replace(app.state.config, defer_document_scans=True)
    scanner = CleanScanner()
    with patch.object(scanner, 'scan', side_effect=AssertionError('HTTP worker ran scanner')):
        record, document_id, _ = upload(documents, scanner)
    assert client.get(f'/contracts/{record}/documents/{document_id}').status_code == 409
    with owner.state.session_factory() as db:
        job = db.get(DocumentJob, document_id)
        assert (job.state, job.attempts) == ('pending', 0)
        assert db.get(ContractDocument, document_id).state == 'quarantined'


@pytest.mark.postgresql
def test_scan_batch_retries_bounded_and_idempotent(documents, request):
    if request.config.getoption('--database') != 'postgresql':
        pytest.skip('Coordinator requires actual PostgreSQL')
    client, app, owner = documents
    app.state.config = replace(app.state.config, defer_document_scans=True)
    record, document_id, _ = upload(documents)
    def run(scanner):
        return scan_batch(owner.state.engine, owner.state.session_factory,
                          app.state.config, scanner, limit=1)
    bad = run(ResultScanner('unavailable'))
    assert bad['reserved'] == bad['retry'] == 1
    assert run(CleanScanner())['reserved'] == 0  # durable backoff, no tight loop
    with owner.state.session_factory() as db:
        job = db.get(DocumentJob, document_id)
        assert job.attempts == 1
        job.updated_at = now_utc()-timedelta(hours=1)
        db.commit()
    result = run(CleanScanner())
    assert result['available'] == result['reserved'] == 1
    assert run(CleanScanner())['reserved'] == 0
    with owner.state.session_factory() as db:
        assert db.get(DocumentJob, document_id).attempts == 2
    assert client.get(f'/contracts/{record}/documents/{document_id}').status_code == 200
    with pytest.raises(PermissionError):
        scan_batch(app.state.engine, app.state.session_factory, app.state.config, CleanScanner())


@pytest.mark.postgresql
def test_scan_batch_reservation_survives_crash_and_exhausts_safely(documents, request):
    if request.config.getoption('--database') != 'postgresql':
        pytest.skip('Coordinator requires actual PostgreSQL')
    client, app, owner = documents
    app.state.config = replace(app.state.config, defer_document_scans=True)
    record, document_id, _ = upload(documents)
    def run():
        return scan_batch(owner.state.engine, owner.state.session_factory,
                          app.state.config, CleanScanner(), limit=1)
    with patch('app.operations.process_document', side_effect=RuntimeError('synthetic interruption')):
        assert run()['errors'] == 1
    with owner.state.session_factory() as db:
        job = db.get(DocumentJob, document_id)
        assert job.attempts == 1 and job.last_error == 'worker_interrupted'
        job.attempts = 5
        job.updated_at = now_utc()-timedelta(hours=1)
        db.commit()
    assert run()['exhausted'] == 1 and run()['reserved'] == 0
    assert client.get(f'/contracts/{record}/documents/{document_id}').status_code == 409


@pytest.mark.postgresql
def test_scan_coordinator_lock_archive_and_count_limit(documents, request):
    if request.config.getoption('--database') != 'postgresql':
        pytest.skip('Coordinator requires actual PostgreSQL')
    _, app, owner = documents
    app.state.config = replace(app.state.config, defer_document_scans=True)
    record, document_id, _ = upload(documents)
    def run(**kwargs):
        return scan_batch(owner.state.engine, owner.state.session_factory,
                          app.state.config, CleanScanner(), **kwargs)
    with owner.state.engine.connect() as lock:
        lock.execute(text('SELECT pg_advisory_lock(:key)'), {'key':SCAN_LOCK})
        lock.commit()
        try:
            assert run()['acquired'] is False
        finally:
            lock.execute(text('SELECT pg_advisory_unlock(:key)'), {'key':SCAN_LOCK})
            lock.commit()
    with owner.state.session_factory() as db:
        db.get(Contract, record).archived_at = now_utc()
        db.commit()
    assert run()['reserved'] == 0
    with owner.state.session_factory() as db:
        assert db.get(DocumentJob, document_id).attempts == 0
    for kwargs in ({'limit':0}, {'limit':101}, {'seconds':0}, {'seconds':601}):
        with pytest.raises(ValueError):
            run(**kwargs)


@pytest.mark.postgresql
def test_automated_scan_rechecks_uploader_after_external_scan(documents, request):
    if request.config.getoption('--database') != 'postgresql':
        pytest.skip('Coordinator requires actual PostgreSQL')
    client, app, owner = documents
    app.state.config = replace(app.state.config, defer_document_scans=True)
    record, document_id, _ = upload(documents)
    class RevokeWhileScanning:
        def scan(self, data):
            with owner.state.session_factory() as db:
                document = db.get(ContractDocument, document_id)
                db.get(User, document.uploaded_by_id).is_active = False
                db.commit()
            return CleanScanner().scan(data)
    result = scan_batch(owner.state.engine, owner.state.session_factory,
                        app.state.config, RevokeWhileScanning())
    assert result['suspended'] == 1 and result['available'] == 0
    with owner.state.session_factory() as db:
        assert db.get(ContractDocument, document_id).state == 'quarantined'
        assert db.get(DocumentJob, document_id).attempts == 1
