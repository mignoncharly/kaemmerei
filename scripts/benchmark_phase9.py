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


def benchmark(*, contracts=10000, documents=50000, users=10, rounds=5, mixed=False, real_scanner=False):
    if not 1 <= contracts <= 10000 or not 0 <= documents <= 50000 or not 1 <= users <= 10 or not 1 <= rounds <= 20:
        raise ValueError('Workload exceeds approved bounded synthetic limits')
    result = dict(dataset=dict(contracts=contracts,documents=documents,concurrent_users=users),
                  profile='Undated draft contracts, no revision history/tasks/reviews, external-link metadata without files; initial read-load baseline only',
                  source_hashes={str(p):sha256(p.read_bytes()).hexdigest() for p in
                    (Path('app/main.py'),Path('app/models.py'),Path('app/financial.py'),
                     Path('alembic/versions/0022_read_admission.py'),Path('alembic/versions/0024_history_materialization.py'),
                     Path('alembic/sql/0025_history_series.sql'),
                     Path('alembic/sql/0026_history_projection.sql'),
                     Path('scripts/synthetic_workload.py'),Path('scripts/benchmark_phase9.py'))},
                  scope='In-process TestClient, actual restricted PostgreSQL logins, synthetic metadata only; not TLS/network/antivirus throughput',
                  targets=dict(page_p95_seconds=2,export_seconds=15), selections=[])
    if mixed:
        result['profile'] = 'Dated synthetic contracts, unknown/zero/known values, 2 historical revisions per contract, 10% tasks/reviews, 500 inert 64KiB PDFs; simultaneous reads/writes/login/download/export'
    with runtime_environment() as runtime:
        if real_scanner:
            import os
            from dataclasses import replace
            from app.documents import ClamAVScanner
            if not os.getenv('CLAMAV_EXECUTABLE'):
                raise ValueError('Explicit actual scanner required for this workload')
            scanner_settings=replace(runtime.app.state.config,
                clamav_executable=Path(os.environ['CLAMAV_EXECUTABLE']),
                clamav_database_dir=Path(os.environ['CLAMAV_DATABASE_DIR']) if os.getenv('CLAMAV_DATABASE_DIR') else None)
            runtime.app.state.document_scanner=ClamAVScanner(scanner_settings)
            if runtime.app.state.document_scanner.scan(b'Synthetic preflight').outcome!='clean':
                raise ValueError('Actual scanner preflight failed')
        result['scanner']='actual ClamAV' if real_scanner else 'synthetic deterministic scanner; no antivirus throughput claim'
        owner = runtime.owner
        with owner.state.session_factory() as db:
            actor = db.scalar(select(User.id).where(User.username=='admin'))
            department_ids = db.scalars(select(Department.id).where(Department.is_active.is_(True))).all()
            password_hash = ph.hash(PASSWORD)
            db.add_all(User(username=f'load_{n}',password_hash=password_hash,role='department' if mixed else 'admin',
                       department_id=department_ids[n%len(department_ids)] if mixed else None,is_active=True)
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
        if mixed:
            from scripts.synthetic_workload import enrich
            result['dataset'].update(enrich(owner, ids, actor, files=min(500,documents)))
            # All read-model rows were created by the explicit synthetic owner;
            # timed mutations below use actual restricted department HTTP users.
            with owner.state.session_factory() as db:
                rows=db.execute(select(ContractDocument.contract_id,ContractDocument.id)
                    .where(ContractDocument.state=='available').order_by(ContractDocument.id)).all()
                file_by_contract=dict(rows)
        with ExitStack() as stack:
            clients=[stack.enter_context(TestClient(runtime.app)) for _ in range(users)]
            for i,client in enumerate(clients):
                assert login(client,f'load_{i}').status_code==303
            # Mixed waves interleave operations across independent scoped users.
            if mixed:
                from io import BytesIO
                from tests.support import csrf_from, workflow_payload
                operations=('dashboard','reports','history_detail','bounded_export','upload_scan','task_create','review_create','login','download')
                samples={name:[] for name in operations}
                timed_login=[False]*users
                def mixed_request(item):
                    index,client,kind=item
                    cid=ids[index%len(department_ids)]
                    started=monotonic()
                    try:
                        if kind=='login':
                            client.cookies.clear(); response=login(client,f'load_{index}'); expected=303
                        elif kind in ('task_create','review_create','upload_scan'):
                            suffix={'task_create':'tasks','review_create':'reviews','upload_scan':'documents'}[kind]
                            path=f'/contracts/{cid}/{suffix}'
                            data=workflow_payload(client,path,{'csrf_token':csrf_from(client.get('/').text)})
                            if kind=='task_create':data.update(title='Synthetic concurrent task',kind='review')
                            if kind=='review_create':data.update(recipient='Kämmerei',subject='Synthetic concurrent review')
                            kwargs={'files':{'documents':('synthetic.pdf',BytesIO(b'%PDF-1.4\nSynthetic request'),'application/pdf')}} if kind=='upload_scan' else {}
                            response=client.post(path,data=data,follow_redirects=False,**kwargs);expected=303
                        else:
                            path={'dashboard':'/','reports':'/reports','history_detail':f'/contracts/{cid}',
                                'bounded_export':'/contracts/export.xlsx?q=Synthetic+0000',
                                'download':f'/contracts/{cid}/documents/{file_by_contract.get(cid,0)}'}[kind]
                            response=client.get(path);expected=200
                        if kind=='bounded_export' and 'spreadsheetml' not in response.headers.get('content-type',''):
                            expected=-1
                        if kind=='download' and not response.content.startswith(b'%PDF-'):
                            expected=-1
                        if kind!='login' and (response.url.path=='/login' or response.headers.get('location','').startswith('/login')):
                            expected=-1
                        return kind,dict(seconds=monotonic()-started,status=response.status_code,expected=expected,bytes=len(response.content))
                    except Exception:
                        return kind,dict(seconds=monotonic()-started,status=0,expected=200,bytes=0)
                with ThreadPoolExecutor(max_workers=users) as pool:
                    for wave in range(rounds*len(operations)):
                        batch=[]
                        for i,c in enumerate(clients):
                            kind=operations[(wave+i)%len(operations)]
                            if kind=='login':
                                # Ordinary pilot use: initial login plus one
                                # timed reauthentication per user. Repeated
                                # spraying from one IP is a separate negative
                                # security test, not successful ordinary load.
                                if timed_login[i]:kind='history_detail'
                                else:timed_login[i]=True
                            batch.append((i,c,kind))
                        for kind,sample in pool.map(mixed_request,batch):samples[kind].append(sample)
                for kind,values in samples.items():
                    p95=percentile([s['seconds'] for s in values],.95)
                    # Adopted 2s ordinary-page and 15s export targets; other
                    # operations measured under a separate 15s engineering cap.
                    threshold=2 if kind in ('dashboard','reports','history_detail','download') else 15
                    result['selections'].append(dict(operation=kind,requests=len(values),p95_seconds=p95,
                        max_seconds=max(s['seconds'] for s in values),target_seconds=threshold,
                        statuses={str(code):sum(s['status']==code for s in values) for code in sorted({s['status'] for s in values})},
                        passed=all(s['status']==s['expected'] for s in values) and p95<threshold))
                    print(json.dumps(result['selections'][-1]),flush=True)
                # Real department isolation under the same loaded dataset.
                result['isolation_passed']=all(c.get(f'/contracts/{ids[(i+1)%len(department_ids)]}').status_code==404
                    for i,c in enumerate(clients))
            # Each read-only wave submits one request per logged-in account.
            with ThreadPoolExecutor(max_workers=users) as pool:
                for path in (() if mixed else ('/', '/reports', f'/contracts/{ids[0]}',
                             '/contracts/export.xlsx?q=Synthetic+0000')):
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
    result['passed']=all(selection['passed'] for selection in result['selections']) and result.get('isolation_passed',True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contracts',type=int,default=10000)
    parser.add_argument('--documents',type=int,default=50000)
    parser.add_argument('--users',type=int,default=10)
    parser.add_argument('--rounds',type=int,default=5)
    parser.add_argument('--mixed',action='store_true')
    parser.add_argument('--real-scanner',action='store_true')
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
