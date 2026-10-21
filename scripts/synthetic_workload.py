"""Synthetic fixtures only. Caller must use the guarded disposable DB harness."""
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4
from sqlalchemy import insert, select
from app.models import Contract, ContractDocument, ContractReview, ContractTask, Revision
from app.logic import snapshot


def enrich(owner, ids, actor, *, files=500):
    """Dated mixed inventory, unknown/zero amounts, 20k history, tasks/reviews.

    These are input variations, never approved finance/legal examples.
    Real inert PDFs replace link metadata; no remote scanner or website touched.
    """
    with owner.state.session_factory() as db:
        if not owner.state.engine.url.database.startswith('ohvr_test_'):
            raise ValueError('Marked synthetic PostgreSQL fixture required')
        for start in range(0, len(ids), 250):
            contracts = db.scalars(select(Contract).where(Contract.id.in_(ids[start:start+250])).order_by(Contract.id)).all()
            history = []; tasks = []; reviews = []
            for c in contracts:
                c.status=('draft','in_progress','terminated','ended')[c.id%4]
                c.end_date = date(2026 + c.id % 3, 2, 28)
                c.notice_period_months = c.id % 7
                c.automatic_renewal = c.id % 3 == 0
                c.renewal_period_months = 12 if c.automatic_renewal else None
                c.annual_value = None if c.id % 5 == 0 else Decimal(c.id % 1000)
                c.value_basis = ('unknown', 'net', 'gross')[c.id % 3]
                c.financial_direction = (None, 'income', 'expense')[c.id % 3]
                state = snapshot(c)
                for year in (2024, 2025):
                    history.append(dict(contract_id=c.id, actor_id=actor, action='created' if year==2024 else 'updated',
                        after=state, created_at=datetime(year, 1, 1)))
                if c.id % 10 == 0:
                    tasks.append(dict(contract_id=c.id, title='Synthetic manual deadline', kind='review',
                        due_date=date(2026, 10, 20), created_by_id=actor))
                    reviews.append(dict(contract_id=c.id, recipient='Kämmerei', subject='Synthetic review',
                        content_revision=1, created_by_id=actor))
            db.execute(insert(Revision), history)
            if tasks:
                db.execute(insert(ContractTask), tasks); db.execute(insert(ContractReview), reviews)
            db.commit()
        documents = db.scalars(select(ContractDocument).where(ContractDocument.provenance=='external_link')
            .order_by(ContractDocument.id).limit(files)).all()
        payload = b'%PDF-1.4\nSynthetic inert workload fixture\n' + b'0' * (64*1024)
        digest = sha256(payload).hexdigest()
        for document in documents:
            key = uuid4().hex + '.pdf'
            (owner.state.document_storage_dir/'blobs'/key).write_bytes(payload)
            document.storage_key = key; document.external_url = None
            document.original_filename = 'synthetic.pdf'; document.content_type = 'application/pdf'
            document.verified_media_type = 'application/pdf'; document.provenance = 'upload'
            document.state = 'available'; document.scan_result = 'clean'
            document.scanner_version = 'synthetic-fixture-not-antivirus'; document.sha256 = digest
            document.size_bytes = len(payload)
        db.commit()
    return dict(history=len(ids)*2, tasks=len(ids)//10, reviews=len(ids)//10,
                actual_files=len(documents), file_bytes=len(documents)*len(payload),
                statuses=['draft','in_progress','terminated','ended'])


def seed_recovery(owner, actor, *, contracts=10000, documents=50000):
    from sqlalchemy import func
    with owner.state.session_factory() as db:
        existing = db.scalar(select(func.count()).select_from(Contract))
        for start in range(existing, contracts, 250):
            db.execute(insert(Contract), [dict(contract_number=f'REC-{i:07d}',
                designation=f'Synthetic recovery {i:07d}', contract_type='Miete', relevant_date=date(2026,1,1),
                department_id=1+i%2, created_by_id=actor, updated_by_id=actor)
                for i in range(start,min(start+250,contracts))])
            db.commit()
        ids = db.scalars(select(Contract.id).order_by(Contract.id)).all()
        existing = db.scalar(select(func.count()).select_from(ContractDocument))
        for start in range(existing, documents, 250):
            db.execute(insert(ContractDocument), [dict(contract_id=ids[i%len(ids)], uploaded_by_id=actor,
                original_filename='Synthetic recovery link', external_url='https://dms.example.invalid/synthetic',
                content_type='application/x-dms-link', size_bytes=0,state='link',scan_result='not_applicable',
                provenance='external_link') for i in range(start,min(start+250,documents))])
            db.commit()
    return enrich(owner, ids, actor)
