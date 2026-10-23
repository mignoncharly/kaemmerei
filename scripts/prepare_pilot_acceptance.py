"""Build a source-bound synthetic participant packet; never grants acceptance."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile,ZIP_DEFLATED
from scripts.pilot_verification import ROOT,source_identity,validate_acceptance
from scripts.browser_diagnostics import browser_result

BROWSER_PATHS=['app','alembic','scripts/verify_phase8_browser.py','scripts/pilot_browser_checks.py',
               'scripts/browser_diagnostics.py','scripts/run_pilot_verification.py','scripts/pilot_verification.py',
               'scripts/Invoke-PilotBrowserVerification.ps1','tests/support.py','tests/scanner_support.py',
               'requirements.txt','requirements.lock','requirements-dev.txt','requirements-browser.txt']


def validate_browser(run,expected_source,expected_hash,candidate):
    from app.documents import reject_links
    run=Path(run).absolute();reject_links(run);run=run.resolve()
    if not run.is_relative_to(ROOT/'.verification'):raise ValueError('Local evidence required')
    paths=[run/'sanitized-report.json',run/'execution/sanitized-report.json',run/'execution/browser/result.json']
    for path in paths:reject_links(path)
    wrapper,parent,result=[json.loads(p.read_text(encoding='utf-8-sig')) for p in paths]
    actual=sha256(paths[2].read_bytes()).hexdigest()
    if actual!=expected_hash:raise ValueError('Browser result hash mismatch')
    passed,details=browser_result(paths[2],expected_source,parent['started_at'],parent['exit_code'])
    if (not passed or parent.get('format')!='ohvr-revision-verification-v1' or parent.get('selection')!='browser'
            or parent.get('status')!='VERIFIED' or parent.get('synthetic_only') is not True
            or parent.get('source')!=expected_source or parent.get('result_sha256')!=actual
            or wrapper.get('format')!='ohvr-local-browser-verification-v2' or wrapper.get('status')!='passed'
            or wrapper.get('exit_code')!=0 or wrapper.get('synthetic_only') is not True
            or wrapper.get('source')!=expected_source or wrapper.get('result_sha256')!=actual
            or wrapper.get('check_count')!=details['check_count'] or wrapper.get('error_code') is not None
            or wrapper.get('failing_stage') is not None):
        raise ValueError('Browser evidence identity or outcome mismatch')
    if subprocess.run(['git','merge-base','--is-ancestor',expected_source,candidate],cwd=ROOT).returncode:
        raise ValueError('Browser source is not a candidate ancestor')
    if subprocess.run(['git','diff','--quiet',expected_source,candidate,'--',*BROWSER_PATHS],cwd=ROOT).returncode:
        raise ValueError('Browser-affecting source changed; new browser verification required')
    return {'status':'VERIFIED','source':expected_source,'result_sha256':actual,
            'check_count':details['check_count'],'browser_version':result.get('browser_version'),
            'candidate_browser_inputs_unchanged':True,
            'formal_participant_acceptance':False}


def build(output,source,browser):
    from app.documents import reject_links
    output=Path(output).absolute();reject_links(output);output=output.resolve()
    if not output.is_relative_to(ROOT/'.verification'):raise ValueError('Local packet output required')
    output.mkdir(parents=True,exist_ok=False)
    packet=json.loads((ROOT/'docs/pilot/scenarios-v1.json').read_text(encoding='utf-8'))
    results=json.loads((ROOT/'docs/pilot/results.template.json').read_text(encoding='utf-8'))
    results['source']=source
    review=validate_acceptance(packet,results,source)
    if review['counts']['NOT_RUN']!=12:raise ValueError('Acceptance packet must start with twelve unexecuted scenarios')
    payloads={'scenarios.json':json.dumps(packet,ensure_ascii=False,indent=2)+'\n',
              'results.json':json.dumps(results,ensure_ascii=False,indent=2)+'\n',
              'browser-evidence.json':json.dumps(browser,indent=2)+'\n',
              'authorization.json':json.dumps({'source':source,'synthetic_only':True,
                 'formal_pilot_acceptance':'NOT_GRANTED','real_data_authorization':'NOT_GRANTED',
                 'production_authorization':'NOT_GRANTED','independent_security_review':'NOT_COMPLETED',
                 'finance_deadline_records_rules':'PENDING_MUNICIPAL_CLARIFICATION','automated_disposal_enabled':False},indent=2)+'\n',
              'fixtures/synthetic.txt':'Synthetic acceptance attachment. No municipal data.\n',
              'fixtures/synthetic.pdf':b'%PDF-1.4\n% Synthetic inert scanner fixture, not a rendered document.\n',
              'SESSION.md':"""# Synthetic pilot acceptance session

Candidate source: SOURCE
Participants: responsible Kämmerei representative; selected Kämmerei test users;
selected Fachbereich user; product owner/software engineer/project IT operator.
Record participant roles, session date/timezone and local evidence references below.
No identities, credentials, TOTP seeds/codes, real contracts or authenticated URLs
belong in shared evidence. The account administrator only provisions the approved
configurable business permissions; no additional Judith or infrastructure grants.

Start with an empty disposable register. Create SYN-PILOT-FB-001 (fictional equipment
maintenance) and SYN-PILOT-KAM-001 (fictional rental), with synthetic contacts. Enter
all dates manually. Use unknown and known-zero amounts; no unapproved accounting,
renewal or contractual-deadline interpretation. Use isolated browser profiles.
PILOT-006/007 require an approved actual scanner; otherwise record BLOCKED.
PILOT-008 requires an independently assigned reviewer with existing read scope.
PILOT-010 uses disposable restore targets; no live service changes. Record actual
assistive technology for PILOT-011. Local SQLite/Edge automation is supporting
evidence and does not replace participant, restricted PostgreSQL or host acceptance.

Execute each case in SCENARIOS.md. Edit only results.json: leave NOT_RUN for untouched
cases, BLOCKED for missing dependencies, FAILED for observed failures. A PASSED row
requires participant_role, timezone-bearing observed_at, actual and evidence_reference.
Never copy the automated 32-check pass into the twelve participant outcomes.

Validate using the repository at the candidate source:
python -m scripts.pilot_verification --expected-source SOURCE --output .verification/acceptance-review-UNIQUE.json acceptance --results PATH_TO_RESULTS
Exit 2 is expected while any scenario is not PASSED. Validation never grants formal
pilot acceptance, real-data authorization or production approval. Obtain and record
those separate decisions through the existing municipal process. No external
notifications, recovery-key escrow, automatic disposal or deployment is activated.
""".replace('SOURCE',source)}
    lines=['# Twelve participant scenarios','',f'Candidate source: `{source}`','']
    for row in packet['scenarios']:
        lines.extend([f"## {row['id']} - {row['title']}",'',f"Participant: {row['participant_role']}",'',
                      row['steps'],'',f"Expected: {row['expected']}",'','Actual result: NOT_RUN',''])
    payloads['SCENARIOS.md']='\n'.join(lines)
    for name,data in payloads.items():
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data if isinstance(data,bytes) else data.encode('utf-8'))
    manifest={'format':'ohvr-synthetic-acceptance-package-v1','source':source,'synthetic_only':True,
              'formal_acceptance_complete':False,'scenario_count':12,'participant_results':review,
              'browser':browser,'files':{n:sha256((output/n).read_bytes()).hexdigest() for n in sorted(payloads)}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    archive=output/'acceptance.zip'
    with ZipFile(archive,'x',compression=ZIP_DEFLATED) as bundle:
        for name in sorted([*payloads,'manifest.json']):bundle.write(output/name,name)
    manifest['archive_sha256']=sha256(archive.read_bytes()).hexdigest()
    (output/'package-summary.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source',required=True)
    parser.add_argument('--browser-source',required=True)
    parser.add_argument('--browser-result-sha256',required=True)
    parser.add_argument('--browser-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=source_identity(args.expected_source)
    evidence=validate_browser(args.browser_run,args.browser_source,args.browser_result_sha256,source)
    report=build(args.output,source,evidence)
    source_identity(source)
    print(json.dumps(report))


if __name__=='__main__':main()
