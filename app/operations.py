"""Bounded native PostgreSQL scan coordinator. No storage deletion or delivery.

Uses explicit operator credentials, never the web/integration/maintenance role.
The session advisory lock is released on connection death; durable reservations
survive process crashes. Run against direct PostgreSQL, not transaction pooling.
"""
from contextlib import contextmanager
from datetime import timedelta
from time import monotonic

from sqlalchemy import case, func, select, text

from app.documents import process_document
from app.identity_service import lock_identities
from app.models import Contract, ContractDocument, DocumentJob, now_utc

SCAN_LOCK = 724931822
MAX_ATTEMPTS = 5


def publish_events(engine, *, limit=500):
    """Bounded atomic publication under the API's existing sequencing lock.

    No event/cursor/snapshot retention deletion while records policy is pending.
    """
    from app.monitoring import require_operator
    from app.models import SyncState, SyncOutbox, SyncEvent
    from app.db import make_session_factory
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('Event batch must be 1..500')
    if engine.dialect.name != 'postgresql':
        raise ValueError('Scheduled publication requires PostgreSQL')
    with engine.connect() as connection:
        require_operator(connection)
    with make_session_factory(engine)() as db:
        state = db.scalar(select(SyncState).where(SyncState.id == 1).with_for_update())
        rows = db.scalars(select(SyncOutbox).where(SyncOutbox.published_seq.is_(None))
                          .order_by(SyncOutbox.id).limit(limit)).all()
        for row in rows:
            state.next_seq += 1
            db.add(SyncEvent(seq=state.next_seq, event_key=row.event_key,
                contract_id=row.contract_id, old_department_id=row.old_department_id,
                new_department_id=row.new_department_id, kind=row.kind))
            row.published_seq = state.next_seq
        db.commit()
        return {'published': len(rows), 'retention_deletion': False}


@contextmanager
def scan_coordinator(engine):
    if engine.dialect.name != 'postgresql':
        raise ValueError('Scheduled scan coordinator requires native PostgreSQL')
    with engine.connect() as connection:
        owner = connection.scalar(text("""SELECT pg_get_userbyid(relowner)=current_user
            FROM pg_class WHERE oid='public.document_jobs'::regclass"""))
        if not owner:
            raise PermissionError('Scan coordinator requires the explicit schema operator')
        acquired = connection.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': SCAN_LOCK})
        connection.commit()
        try:
            yield bool(acquired)
        finally:
            if acquired:
                connection.rollback()
                released = connection.scalar(text('SELECT pg_advisory_unlock(:key)'), {'key': SCAN_LOCK})
                connection.commit()
                if not released:
                    raise RuntimeError('Scan coordinator lost its session lock')


def eligible_jobs(clock):
    # Bounded SQL selection, not a Python scan of the entire queue. Pending jobs
    # reserved by a crashed process obey the same persisted retry delay.
    delay = case((DocumentJob.attempts <= 1, clock-timedelta(minutes=1)),
                 (DocumentJob.attempts == 2, clock-timedelta(minutes=2)),
                 (DocumentJob.attempts == 3, clock-timedelta(minutes=4)),
                 else_=clock-timedelta(minutes=8))
    return (select(DocumentJob.document_id)
        .join(ContractDocument, ContractDocument.id == DocumentJob.document_id)
        .join(Contract, Contract.id == DocumentJob.contract_id)
        .where(DocumentJob.state.in_(('pending', 'retry')),
               DocumentJob.attempts < MAX_ATTEMPTS,
               (DocumentJob.attempts == 0) | (DocumentJob.updated_at <= delay),
               Contract.archived_at.is_(None),
               ContractDocument.provenance == 'upload',
               ContractDocument.state.in_(('pending', 'quarantined')))
        .order_by(DocumentJob.updated_at, DocumentJob.document_id))


def scan_batch(engine, sessions, settings, scanner, *, limit=10, seconds=120):
    if not 1 <= limit <= 100 or not 1 <= seconds <= 600:
        raise ValueError('Scan batch must have bounded count and launch deadline')
    started = monotonic()
    result = dict(acquired=False, reserved=0, available=0, rejected=0,
                  retry=0, suspended=0, unchanged=0, errors=0, exhausted=0)
    with scan_coordinator(engine) as acquired:
        result['acquired'] = acquired
        if not acquired:
            return result
        # A fixed bounded batch prevents newly arriving work from extending a run.
        with sessions() as db:
            candidates = db.scalars(eligible_jobs(now_utc()).limit(limit)).all()
        for document_id in candidates:
            if monotonic()-started >= seconds:
                break
            with sessions() as db:
                lock_identities(db)
                # Revalidate live state after lock; inline/dev work may have won.
                if db.scalar(eligible_jobs(now_utc()).where(
                        DocumentJob.document_id == document_id)) is None:
                    db.rollback()
                    continue
                job = db.get(DocumentJob, document_id)
                job.attempts += 1
                job.updated_at = now_utc()
                job.last_error = 'worker_interrupted'
                db.commit()  # Reservation survives interruption before/during scan.
                result['reserved'] += 1
                try:
                    state = process_document(db, settings, scanner, document_id,
                                             count_attempt=False,enforce_upload_authority=True)
                    bucket = {'available':'available', 'rejected':'rejected',
                              'quarantined':'retry','suspended':'suspended'}.get(state, 'unchanged')
                    result[bucket] += 1
                except Exception:
                    db.rollback()
                    # Do not log exception text (paths, URLs and scanner output).
                    # Preserve the committed reservation and quarantine for retry.
                    result['errors'] += 1
        with sessions() as db:
            result['exhausted'] = db.scalar(select(func.count()).select_from(DocumentJob)
                .join(ContractDocument, ContractDocument.id == DocumentJob.document_id)
                .join(Contract, Contract.id == DocumentJob.contract_id)
                .where(DocumentJob.state.in_(('pending', 'retry')),
                       DocumentJob.attempts >= MAX_ATTEMPTS,
                       Contract.archived_at.is_(None),
                       ContractDocument.state.in_(('pending', 'quarantined'))))
    return result
