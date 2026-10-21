"""Opt-in synthetic PostgreSQL workload; reuses guarded UUID test harness.

No target database argument: this cannot benchmark or seed a business database.
Runs real restricted-role HTTP operations in-process, not production TLS/network.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import date
import json
from math import ceil
from hashlib import sha256
from pathlib import Path
from time import monotonic

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select

from app.models import Contract, ContractDocument, Department, User
from app.security import ph
from tests.runtime_support import runtime_environment
from tests.support import PASSWORD, login


def percentile(values, quantile):
    return sorted(values)[max(0, ceil(len(values)*quantile)-1)]


def benchmark(*, contracts=10000, documents=50000, users=10, rounds=5):
    if not 1 <= contracts <= 10000 or not 0 <= documents <= 50000 or not 1 <= users <= 10 or not 1 <= rounds <= 20:
        raise ValueError('Workload exceeds approved bounded synthetic limits')
    result = dict(dataset=dict(contracts=contracts,documents=documents,concurrent_users=users),
                  profile='Undated draft contracts, no revision history/tasks/reviews, external-link metadata without files; initial read-load baseline only',
                  source_hashes={str(p):sha256(p.read_bytes()).hexdigest() for p in
                    (Path('app/main.py'),Path('app/models.py'),Path('app/financial.py'),
                     Path('alembic/versions/0022_read_admission.py'),Path('scripts/benchmark_phase9.py'))},
                  scope='In-process TestClient, actual restricted PostgreSQL logins, synthetic metadata only; not TLS/network/antivirus throughput',
                  targets=dict(page_p95_seconds=2,export_seconds=15), selections=[])
    with runtime_environment() as runtime:
        owner = runtime.owner
        with owner.state.session_factory() as db:
            actor = db.scalar(select(User.id).where(User.username=='admin'))
            department_ids = db.scalars(select(Department.id).where(Department.is_active.is_(True))).all()
            password_hash = ph.hash(PASSWORD)
            db.add_all(User(username=f'load_{n}',password_hash=password_hash,role='admin',is_active=True)
                       for n in range(users))
            db.commit()
            for start in range(0,contracts,250):
                db.execute(insert(Contract), [dict(contract_number=f'SYN-{i:07d}',
                    designation=f'Synthetic {i:07d}',contract_type='Miete', relevant_date=date(2026,1,1),
                    department_id=department_ids[i%len(department_ids)],created_by_id=actor,updated_by_id=actor)
                    for i in range(start,min(start+250,contracts))])
                db.commit()
            ids = db.scalars(select(Contract.id).order_by(Contract.id)).all()
            for start in range(0,documents,250):
                db.execute(insert(ContractDocument), [dict(contract_id=ids[i%len(ids)],uploaded_by_id=actor,
                    original_filename='Synthetic external metadata',external_url='https://dms.example.invalid/synthetic',
                    content_type='application/x-dms-link',size_bytes=0,state='link',scan_result='not_applicable',
                    provenance='external_link') for i in range(start,min(start+250,documents))])
                db.commit()
            assert db.scalar(select(func.count()).select_from(Contract))==contracts
            assert db.scalar(select(func.count()).select_from(ContractDocument))==documents
        with ExitStack() as stack:
            clients=[stack.enter_context(TestClient(runtime.app)) for _ in range(users)]
            for i,client in enumerate(clients):
                assert login(client,f'load_{i}').status_code==303
            # Each wave submits one request per independent logged-in account.
            with ThreadPoolExecutor(max_workers=users) as pool:
                for path in ('/', '/reports', f'/contracts/{ids[0]}',
                             '/contracts/export.xlsx?q=Synthetic+0000'):
                    def request(client):
                        started=monotonic()
                        try:
                            response=client.get(path)
                            return dict(seconds=monotonic()-started,status=response.status_code,bytes=len(response.content))
                        except Exception:
                            return dict(seconds=monotonic()-started,status=0,bytes=0)
                    samples=[]
                    for _ in range(rounds):
                        samples.extend(pool.map(request,clients))
                    durations=[sample['seconds'] for sample in samples]
                    export='export.xlsx' in path
                    threshold=15 if export else 2
                    p95=percentile(durations,0.95)
                    result['selections'].append(dict(operation='bounded_export' if export else path,
                        requests=len(samples),statuses={str(code):sum(s['status']==code for s in samples)
                        for code in sorted({s['status'] for s in samples})},p95_seconds=p95,
                        max_seconds=max(durations),max_response_bytes=max(s['bytes'] for s in samples),
                        passed=all(s['status']==200 for s in samples) and p95<threshold))
                    print(json.dumps(result['selections'][-1]),flush=True)
    result['passed']=all(selection['passed'] for selection in result['selections'])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contracts',type=int,default=10000)
    parser.add_argument('--documents',type=int,default=50000)
    parser.add_argument('--users',type=int,default=10)
    parser.add_argument('--rounds',type=int,default=5)
    parser.add_argument('--output',type=Path,required=True)
    args=vars(parser.parse_args());output=args.pop('output')
    if output.exists():
        raise SystemExit('Refusing to overwrite existing benchmark evidence; choose a new output path')
    result=benchmark(**args)
    with output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 2)


if __name__=='__main__':
    main()
