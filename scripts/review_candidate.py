"""Local-only review manifest and retained acceptance verification; no network operations."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
from zipfile import ZipFile
import yaml
from scripts.pilot_verification import ROOT,source_identity,write_report

REPOSITORY='https://github.com/mignoncharly/kaemmerei'
BRANCH='review/u026-synthetic-pilot'
PACKAGE_HASH='ffab0034f7b7d0e924501b625a0e318b830402aec8917ac20024796327acc57f'
PACKAGE_SOURCE='da60deaf6cd89a16b2711a5bad9a0fd377b00215'
BROWSER_SOURCE='d3f5ad2752feb565b5ae74ecbf90fde82ad84e4d'
BROWSER_HASH='2de4e1f138efe1e53f9c73ee902c866840876da6809836fca9cf9b566d69f179'


def verify_package(path):
    from app.documents import reject_links
    path=Path(path).absolute();reject_links(path)
    if sha256(path.read_bytes()).hexdigest()!=PACKAGE_HASH:raise ValueError('Retained U025 archive hash mismatch')
    with ZipFile(path) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        if set(archive.namelist())!=set(manifest['files'])|{'manifest.json'}:raise ValueError('Unexpected package members')
        if archive.testzip() is not None:raise ValueError('Archive CRC mismatch')
        for name,digest in manifest['files'].items():
            if sha256(archive.read(name)).hexdigest()!=digest:raise ValueError('Payload checksum mismatch')
        results=json.loads(archive.read('results.json'));browser=json.loads(archive.read('browser-evidence.json'))
        if manifest['source']!=PACKAGE_SOURCE or results['source']!=PACKAGE_SOURCE:raise ValueError('Package source mismatch')
        if len(results['results'])!=12 or any(r['status']!='NOT_RUN' for r in results['results']):raise ValueError('Retained participant template changed')
        if browser['source']!=BROWSER_SOURCE or browser['result_sha256']!=BROWSER_HASH:raise ValueError('Browser reference changed')
    return {'status':'VERIFIED','archive_sha256':PACKAGE_HASH,'source':PACKAGE_SOURCE,
            'scenarios':12,'participant_cases_executed':0,'formal_acceptance_complete':False}


def ci_matrix(path):
    workflow=yaml.safe_load(Path(path).read_text(encoding='utf-8'));jobs=workflow['jobs'];rows=[]
    expected={'locked-release','release-reproducibility','native-storage-links','frontend-browser',
              'document-scanner','native-postgresql','sqlite','postgresql'}
    if set(jobs)!=expected:raise ValueError('Required CI jobs changed; review the matrix')
    for name,job in jobs.items():
        platforms=job.get('strategy',{}).get('matrix',{}).get('os',[job['runs-on']])
        for platform in platforms:rows.append({'job':name,'platform':platform,'status':'NOT_RUN'})
    if len(rows)!=10:raise ValueError('Expected ten hosted executions')
    return {'workflow':'.github/workflows/phase1-verification.yml','workflow_sha256':sha256(Path(path).read_bytes()).hexdigest(),
            'executions':rows,'required_count':10,'hosted_execution_authorized':False,'hosted_success_claimed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source',required=True)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();source=source_identity(args.expected_source)
    remote=subprocess.check_output(['git','remote','get-url','origin'],cwd=ROOT,text=True).strip();url=urlsplit(remote)
    if url.scheme!='https' or url.hostname!='github.com' or url.username or url.password or url.path.rstrip('/').removesuffix('.git')!='/mignoncharly/kaemmerei':
        raise ValueError('Review target remote does not match')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    if branch!=BRANCH:raise ValueError('Review branch mismatch')
    report={'format':'ohvr-isolated-review-v1','source':source,'repository':REPOSITORY,'remote':'origin','branch':branch,
            'publication_authorized':False,'pushed':False,'workflow_dispatched':False,
            'ci':ci_matrix(ROOT/'.github/workflows/phase1-verification.yml'),'retained_u025_package':verify_package(args.package)}
    report['ci']['committed_workflow_sha256']=sha256(subprocess.check_output(['git','show',source+':.github/workflows/phase1-verification.yml'],cwd=ROOT)).hexdigest()
    source_identity(source);write_report(args.output,report);print(json.dumps(report))


if __name__=='__main__':main()
