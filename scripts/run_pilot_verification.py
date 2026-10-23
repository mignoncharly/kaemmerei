"""Revision-bound local synthetic checks. No installs, database setup or services.

Private stdout/stderr stays in private.log. Share only sanitized-report.json.
An unavailable real scanner/browser is not a passing check.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from uuid import uuid4
from scripts.pilot_verification import ROOT,source_identity,write_report


def junit_summary(path):
    root=ET.parse(path).getroot();cases=list(root.iter('testcase'))
    counts={name:sum(c.find(name) is not None for c in cases) for name in ('failure','error','skipped')}
    return {'collected':len(cases),'passed':len(cases)-sum(counts.values()),**counts,
            'skips':[{'test':c.get('classname')+'.'+c.get('name')} for c in cases if c.find('skipped') is not None],
            'passing_subtests':sum(int(s.get('tests','0')) for s in (list(root.findall('testsuite')) if root.tag=='testsuites' else [root]))-len(cases),
            'junit_sha256':sha256(path.read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source',required=True)
    parser.add_argument('--selection',choices=('sqlite','postgresql','mixed','scanner','browser'),required=True)
    parser.add_argument('--channel',choices=('msedge','chrome','chromium'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    from app.documents import reject_links
    source=args.expected_source
    output=args.output.absolute();reject_links(output);output=output.resolve()
    if not output.is_relative_to(ROOT/'.verification'):raise SystemExit('Local verification output required')
    output.mkdir(parents=True,exist_ok=False)
    report={'format':'ohvr-revision-verification-v1','source':source,'selection':args.selection,
            'started_at':datetime.now(timezone.utc).isoformat(),'synthetic_only':True,
            'status':'IMPLEMENTED BUT UNVERIFIED','executed':False,'setup_or_installation_changed':False}
    if args.selection=='browser':
        report.update(check_count=None,failed_check=None)
        browser_run_id=uuid4().hex
    try:source_identity(source)
    except Exception:
        from scripts.browser_diagnostics import diagnostic
        report.update(diagnostic('source_validation_failed','source_validation'))
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        write_report(output/'sanitized-report.json',report)
        print(json.dumps(report))
        raise SystemExit(2)
    env=dict(os.environ)
    if args.selection in ('sqlite','postgresql','scanner'):
        command=[sys.executable,'-u','-m','pytest','-q','--database',args.selection if args.selection!='scanner' else 'sqlite',
                 '--junitxml='+str(output/'junit.xml')]
        if args.selection=='postgresql':env['REQUIRE_BACKUP_ENCRYPTION']='1'
        if args.selection=='scanner':
            command+=['tests/test_phase5.py','-k','real_clamav'];env['REQUIRE_REAL_CLAMAV']='1'
    elif args.selection=='mixed':
        command=[sys.executable,'-u','-m','scripts.benchmark_phase9','--mixed','--output',str(output/'workload.json')]
    else:
        command=[sys.executable,'-u','scripts/verify_phase8_browser.py','--output',str(output/'browser'),
                 '--run-id',browser_run_id]
        if args.channel:command+=['--channel',args.channel]
    # Do not run an unrelated endpoint or install dependencies on behalf of the caller.
    if args.selection=='scanner' and not env.get('CLAMAV_EXECUTABLE'):
        report.update(status='EXTERNALLY_BLOCKED',reason='actual_clamav_not_configured')
    else:
        try:
            with (output/'private.log').open('xb') as log:
                result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        except OSError:
            from scripts.browser_diagnostics import diagnostic
            report.update(diagnostic('verification_launcher_failed','child_execution'))
            report['finished_at']=datetime.now(timezone.utc).isoformat()
            write_report(output/'sanitized-report.json',report)
            print(json.dumps(report))
            raise SystemExit(2)
        report.update(executed=True,exit_code=result.returncode)
        report['status']='VERIFIED' if result.returncode==0 else 'IMPLEMENTED BUT UNVERIFIED'
        if args.selection=='browser':
            from scripts.browser_diagnostics import browser_result
            passed,details=browser_result(output/'browser/result.json',source,report['started_at'],result.returncode,
                                          run_id=browser_run_id)
            report.update(details)
            report['status']='VERIFIED' if passed else 'IMPLEMENTED BUT UNVERIFIED'
        if (output/'junit.xml').is_file():report['tests']=junit_summary(output/'junit.xml')
        for filename in ('workload.json','browser/result.json'):
            path=output/filename
            if path.is_file():report['result_sha256']=sha256(path.read_bytes()).hexdigest()
    try:source_identity(source)
    except Exception:
        report.update(status='IMPLEMENTED BUT UNVERIFIED',reason='source_changed_during_run')
        if args.selection=='browser':
            from scripts.browser_diagnostics import diagnostic
            report.update(diagnostic('source_validation_failed','source_validation'))
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    write_report(output/'sanitized-report.json',report)
    print(json.dumps(report))
    if report['status']!='VERIFIED':raise SystemExit(2)


if __name__=='__main__':main()
