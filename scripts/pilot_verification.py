"""Read-only native/skip/acceptance evidence. Never provisions, patches or deploys.

Run as python -m scripts.pilot_verification. Output is sanitized JSON, created
exclusively under .verification. Pending or failed checks never become passes.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def source_identity(expected=None):
    top=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=ROOT,encoding='utf-8').strip())
    if top.resolve()!=ROOT.resolve():raise ValueError('Verification requires the actual repository root')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if expected and source!=expected:raise ValueError('Source mismatch')
    # Preserve the user's unrelated launcher whitespace without admitting code drift.
    paths=['app','alembic','scripts','tests','.github','docs/pilot','requirements*.txt','requirements.lock',
           ':(exclude)scripts/Start-TestDatabase.ps1']
    if subprocess.run(['git','diff','--quiet','HEAD','--',*paths],cwd=ROOT).returncode:
        raise ValueError('Verification code differs from committed source')
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*paths],cwd=ROOT)
    if untracked.strip():raise ValueError('Uncommitted verification source')
    return source


def write_report(path,report):
    from app.documents import reject_links
    path=Path(path).absolute();reject_links(path);path=path.resolve()
    if not path.is_relative_to(ROOT/'.verification'):raise ValueError('Local verification destination required')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2);stream.write('\n')


def native_report(bin_directory,server=False):
    from app.server_security import validate_client_version,validate_server_version
    import psycopg
    from sqlalchemy.engine import make_url
    report={'format':'ohvr-native-gate-v1','components':{},'server':{'status':'NOT_RUN'},
            'libpq_version_num':psycopg.pq.version(),'libpq_implementation':psycopg.pq.__impl__,
            'installation_changed':False,'scope':'read-only versions/settings; no exploit or application acceptance'}
    for tool in ('pg_dump','pg_restore','psql'):
        path=Path(bin_directory)/(tool+('.exe' if os.name=='nt' else ''))
        item={'status':'EXTERNALLY_BLOCKED'}
        try:
            if not path.is_absolute() or str(path).startswith('\\\\') or not path.is_file():raise ValueError('Explicit existing local tool required')
            data=subprocess.run([str(path),'--version'],capture_output=True,timeout=10,check=True).stdout
            item={'binary_sha256':sha256(path.read_bytes()).hexdigest(),'status':'IMPLEMENTED BUT UNVERIFIED'}
            # Parse observed version separately from baseline validation; never print raw output.
            import re
            match=re.fullmatch(tool.encode()+rb' \(PostgreSQL\) ([0-9]+)\.([0-9]+)(?: \([^\r\n]*\))?\r?\n?',data)
            if match:item['version_num']=int(match[1])*10000+int(match[2])
            validate_client_version(data,tool);item['status']='VERIFIED'
        except Exception:item['reason']='missing_unreviewed_or_below_production_floor'
        report['components'][tool]=item
    if server:
        try:
            url=make_url(os.environ['TEST_POSTGRES_ADMIN_URL'])
            if url.host not in ('127.0.0.1','localhost','::1') or url.database!='postgres':
                raise ValueError('Existing loopback control endpoint required')
            with psycopg.connect(url.set(drivername='postgresql').render_as_string(hide_password=False),
                                  connect_timeout=5,options='-c default_transaction_read_only=on -c statement_timeout=5000') as connection:
                number=int(connection.execute('SHOW server_version_num').fetchone()[0])
                ssl=connection.execute('SHOW ssl').fetchone()[0]=='on'
            item={'status':'IMPLEMENTED BUT UNVERIFIED','version_num':number,'ssl_enabled':ssl}
            try:validate_server_version(number);item['status']='VERIFIED'
            except ValueError:item['reason']='below_reviewed_production_floor'
            report['server']=item
        except Exception:report['server']={'status':'EXTERNALLY_BLOCKED','reason':'read_only_probe_unavailable'}
    major=report['server'].get('version_num',0)//10000
    report['client_server_major_match']=bool(major) and all(i.get('version_num',0)//10000==major for i in report['components'].values())
    report['baseline_passed']=all(i['status']=='VERIFIED' for i in report['components'].values()) and report['server']['status']=='VERIFIED' and report['client_server_major_match']
    report['r43_closed']=False # Patching, actual-host review and repeat acceptance remain separate.
    return report


def junit_cases(path):
    return {(t.get('classname'),t.get('name')):t for t in ET.parse(path).iter('testcase')}


def review_skips(postgresql,sqlite):
    pg,sq=junit_cases(postgresql),junit_cases(sqlite)
    rows=[]
    for backend,cases,other in (('postgresql',pg,sq),('sqlite',sq,pg)):
        for key,case in cases.items():
            skipped=case.find('skipped')
            if skipped is None:continue
            counterpart=other.get(key)
            passed=counterpart is not None and not any(counterpart.find(n) is not None for n in ('skipped','failure','error'))
            rows.append({'backend':backend,'test':'.'.join(key),'reason':skipped.get('message',''),
                         'classification':'EXPECTED_BACKEND_SKIP_COVERED_BY_POSTGRESQL' if backend=='sqlite' and passed else 'MISSING_LOCAL_ENVIRONMENT_COVERAGE',
                         'counterpart_passed':passed})
    return {'format':'ohvr-skip-review-v1','inputs':{str(n):sha256(Path(p).read_bytes()).hexdigest() for n,p in [('postgresql',postgresql),('sqlite',sqlite)]},'skips':rows}


def validate_acceptance(packet,results,source):
    if results.get('source')!=source or results.get('synthetic_only') is not True:
        raise ValueError('Acceptance source/synthetic identity mismatch')
    required={c['id'] for c in packet['scenarios']}
    rows=results.get('results',[])
    if len(rows)!=len(required) or {r['id'] for r in rows}!=required:
        raise ValueError('Exactly one result per required scenario')
    for row in rows:
        if row.get('status') not in ('PASSED','FAILED','NOT_RUN','BLOCKED'):raise ValueError('Invalid outcome')
        if row['status']=='PASSED' and not all(row.get(k) for k in ('participant_role','observed_at','evidence_reference','actual')):
            raise ValueError('Passing participant evidence is incomplete')
        if row.get('observed_at') and datetime.fromisoformat(row['observed_at']).tzinfo is None:
            raise ValueError('Observed acceptance time requires timezone')
    return {'format':'ohvr-pilot-acceptance-review-v1','all_scenarios_passed':all(r['status']=='PASSED' for r in rows),
            'counts':{s:sum(r['status']==s for r in rows) for s in ('PASSED','FAILED','NOT_RUN','BLOCKED')},
            'formal_authorization_granted':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source',required=True);parser.add_argument('--output',type=Path,required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    native=sub.add_parser('native');native.add_argument('--bin',type=Path,required=True);native.add_argument('--server',action='store_true')
    skips=sub.add_parser('skips');skips.add_argument('--postgresql',type=Path,required=True);skips.add_argument('--sqlite',type=Path,required=True)
    accept=sub.add_parser('acceptance');accept.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    try:
        source=source_identity(args.expected_source)
        if args.command=='native':report=native_report(args.bin,args.server)
        elif args.command=='skips':report=review_skips(args.postgresql,args.sqlite)
        else:report=validate_acceptance(json.loads((ROOT/'docs/pilot/scenarios-v1.json').read_text(encoding='utf-8')),json.loads(args.results.read_text(encoding='utf-8')),source)
        if source_identity(source)!=source:raise ValueError('Source changed')
        report.update(source=source,observed_at=datetime.now(timezone.utc).isoformat())
        write_report(args.output,report);print(json.dumps(report))
    except Exception:raise SystemExit('Verification refused or failed; inspect private local inputs; no installation or deployment changed') from None
    if report.get('baseline_passed') is False or report.get('all_scenarios_passed') is False:raise SystemExit(2)


if __name__=='__main__':main()
