"""Read-only engine/definition inventory, never an actual-engine integration pass."""
import argparse
from datetime import date
from hashlib import sha256,file_digest
import json
import os
from pathlib import Path
import re
import subprocess
from scripts.pilot_verification import ROOT,source_identity,write_report


def supported_engine(version,policy,today=None):
    today=today or date.today()
    if not date.fromisoformat(policy['reviewed_on'])<=today<=date.fromisoformat(policy['review_by']):
        raise ValueError('engine_baseline_review_due')
    match=re.fullmatch(r'ClamAV (\d+)\.(\d+)\.(\d+)/\d+/[^\r\n]{1,100}',version.strip())
    if not match:raise ValueError('unrecognized_engine_version')
    major,minor,patch=map(int,match.groups());branch=f'{major}.{minor}'
    approved=policy['approved_upstream_branches'].get(branch)
    if approved is None or patch<approved['minimum_patch']:raise ValueError('engine_below_reviewed_maintenance_baseline')
    return f'{major}.{minor}.{patch}'


def inventory(policy):
    report={'format':'ohvr-scanner-readiness-v1','status':'EXTERNALLY_BLOCKED',
            'real_engine_integration_verified':False,'freshness_verified':False,
            'official_signature_authenticity_verified':False,'installation_changed':False}
    binary=os.getenv('CLAMAV_EXECUTABLE');database=os.getenv('CLAMAV_DATABASE_DIR')
    if not binary or not database:return {**report,'reason':'approved_engine_and_official_definitions_not_configured'}
    try:
        binary=Path(binary);database=Path(database)
        if (not binary.is_absolute() or not binary.is_file() or not database.is_absolute() or not database.is_dir()
                or str(binary).startswith('\\\\') or str(database).startswith('\\\\')):
            raise ValueError('configured_scanner_inputs_unavailable')
        result=subprocess.run([str(binary),'--database='+str(database),'--version'],env={**os.environ,'LC_ALL':'C','TZ':'UTC'},
                              capture_output=True,check=True,timeout=10)
        version=supported_engine(result.stdout.decode('ascii'),policy)
        signatures={}
        for stem in ('main','daily','bytecode'):
            candidates=[database/(stem+ext) for ext in ('.cvd','.cld')]
            found=[p for p in candidates if p.is_file()]
            if stem!='bytecode' and not found:raise ValueError('official_definition_files_missing')
            for path in found:
                with path.open('rb') as handle:signatures[path.name]=file_digest(handle,'sha256').hexdigest()
        report.update(status='READY_FOR_REAL_ENGINE_TESTS',engine_version=version,
                      executable_sha256=sha256(binary.read_bytes()).hexdigest(),definition_sha256=signatures)
    except ValueError as error:
        allowed={'engine_baseline_review_due','unrecognized_engine_version','engine_below_reviewed_maintenance_baseline',
                 'configured_scanner_inputs_unavailable','official_definition_files_missing'}
        report['reason']=str(error) if str(error) in allowed else 'invalid_scanner_baseline_or_inputs'
    except (KeyError,TypeError):report['reason']='invalid_scanner_baseline_or_inputs'
    except (OSError,subprocess.SubprocessError,UnicodeError):report['reason']='scanner_read_only_inventory_failed'
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();source=source_identity(args.expected_source)
    policy_path=ROOT/'docs/pilot/scanner-engine-baseline-v1.json'
    report=inventory(json.loads(policy_path.read_text()))
    report.update(source=source,baseline_sha256=sha256(policy_path.read_bytes()).hexdigest())
    source_identity(source);write_report(args.output,report);print(json.dumps(report))
    if report['status']!='READY_FOR_REAL_ENGINE_TESTS':raise SystemExit(2)


if __name__=='__main__':main()
