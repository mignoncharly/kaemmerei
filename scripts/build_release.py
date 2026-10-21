"""Deterministic committed-source bundle; no deployment, cleanup or key access.

Read Git objects, not the working tree. Uncommitted local changes and ignored
data never enter the artifact. The manifest is integrity metadata, not a release
signature, production acceptance or a copy of third-party runtime tools.
"""
import argparse
import ast
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path,PurePosixPath
import re
import stat
import subprocess
import zipfile

ROOT_FILES=frozenset(('README.md','CHANGELOG.md','alembic.ini','requirements.txt','requirements.lock','.env.example'))
SCRIPTS=frozenset(('scripts/configure_database_roles.py','scripts/render_windows_tasks.py','scripts/build_release.py'))
DOCS=frozenset(('docs/PHASE3_DATABASE_SECURITY.md','docs/PHASE4_WORKFLOW.md','docs/PHASE5_DOCUMENT_LIFECYCLE.md',
    'docs/PHASE6_INTEGRATION_SYNC.md','docs/PHASE7_FINANCE_DATES_EXCEL.md','docs/PHASE8_FRONTEND_NAVIGATION.md',
    'docs/PHASE9_OPERATIONS.md','docs/PHASE10_ACCEPTANCE.md','docs/PILOT_DECISIONS.md',
    'docs/DOMAIN_RULE_REQUIREMENTS.md','docs/HOSTING_ASSESSMENT.md','docs/RELEASE_RUNBOOK.md','docs/NATIVE_SECURITY_BASELINE.md',
    'docs/rules/finance-v1.json','docs/rules/deadlines-v1.json','docs/rules/records-v1.json'))
DEPLOY=frozenset(('deploy/windows/Invoke-Ohvr.ps1','deploy/windows/logging.json',
                  'deploy/windows/Caddyfile.example','deploy/windows/web-config.example.json'))
REQUIRED=frozenset(('app/main.py','alembic/env.py','alembic.ini','requirements.txt','requirements.lock','docs/PHASE9_OPERATIONS.md'))
MAX_FILE=8*1024**2
MAX_TOTAL=64*1024**2
DENIED=frozenset(('data','documents','logs','__pycache__','node_modules','tests','.git','.venv','.wheelhouse','.verification','.local-postgres'))


def allowed(name):
    path=PurePosixPath(name)
    if (str(path)!=name or path.is_absolute() or '..' in path.parts or '\\' in name
            or any(part.lower() in DENIED for part in path.parts)):
        return False
    if name in ROOT_FILES|SCRIPTS|DOCS|DEPLOY:return True
    if path.parts[0]=='alembic':return path.suffix in ('.py','.sql')
    if path.parts[0]=='app':
        if path.suffix in ('.py','.html','.css','.js','.svg','.png','.ico'):return True
        return name=='app/static/api-v2.schema.json'
    return False


def git(root,*args):
    # Source-only commands, no credentials/remotes or Git working-tree mutation.
    return subprocess.run(['git','-C',str(root),*args],stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,check=True,timeout=30).stdout


def migration_head(files):
    revisions={};parents=set()
    for name,data in files.items():
        if not name.startswith('alembic/versions/') or not name.endswith('.py'):continue
        constants={}
        for node in ast.parse(data).body:
            names=[n.id for n in node.targets if isinstance(n,ast.Name)] if isinstance(node,ast.Assign) else (
                [node.target.id] if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) else [])
            for key in names:
                if key in ('revision','down_revision'):constants[key]=ast.literal_eval(node.value)
        revision=constants.get('revision');parent=constants.get('down_revision')
        if not isinstance(revision,str) or revision in revisions:raise ValueError('Invalid release migration graph')
        revisions[revision]=parent
        if parent is not None:
            if not isinstance(parent,str):raise ValueError('Review branched migration graph before release')
            parents.add(parent)
    heads=set(revisions)-parents
    if len(heads)!=1 or parents-set(revisions):raise ValueError('Release must have one complete migration chain')
    head=heads.pop();seen=set();cursor=head
    while cursor is not None:
        if cursor in seen:raise ValueError('Cyclic release migration graph')
        seen.add(cursor);cursor=revisions[cursor]
    if seen!=set(revisions):raise ValueError('Disconnected release migration graph')
    return head


def committed_files(root):
    commit=git(root,'rev-parse','--verify','HEAD^{commit}').decode('ascii').strip()
    if not re.fullmatch('[0-9a-f]{40,64}',commit):raise ValueError('Invalid source identity')
    files={};total=0
    for row in git(root,'ls-tree','-r','-z',commit).split(b'\0'):
        if not row:continue
        metadata,raw_name=row.split(b'\t',1);name=raw_name.decode('utf-8')
        mode,kind,oid=metadata.decode('ascii').split()
        if not allowed(name):
            if name.startswith(('app/','alembic/')):
                raise ValueError('Unclassified tracked runtime object; release review required')
            continue
        if kind!='blob' or mode not in ('100644','100755'):raise ValueError('Linked/submodule release objects forbidden')
        size=int(git(root,'cat-file','-s',oid))
        if size>MAX_FILE or total+size>MAX_TOTAL:raise ValueError('Release exceeds bounded source profile')
        data=git(root,'cat-file','blob',oid)
        if len(data)!=size:raise ValueError('Source object size mismatch')
        files[name]=data;total+=size
    if not REQUIRED<=set(files):raise ValueError('Committed release inputs missing; commit reviewed source first')
    return commit,files


def release_bytes(root):
    commit,files=committed_files(root)
    manifest=dict(format='ohvr-source-release-v1',source_commit=commit,migration_head=migration_head(files),
        python='CPython 3.14',working_tree_included=False,
        dependencies='requirements.lock; --require-hashes --only-binary=:all:',
        scope='Source/configuration templates only; no secrets, runtime tools, data, deployment or acceptance',
        files=[dict(path=name,sha256=sha256(data).hexdigest(),bytes=len(data)) for name,data in sorted(files.items())])
    files['RELEASE-MANIFEST.json']=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode('utf-8')
    buffer=BytesIO()
    # STORED removes zlib/platform/version differences; fixed metadata and order.
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,data)
    return buffer.getvalue(),manifest


def build(root,output):
    if not output.is_absolute() or (os.name=='nt' and str(output).startswith('\\\\')):
        raise ValueError('Explicit local artifact output required')
    for path in (output,*output.parents):
        if path.is_symlink() or path.is_junction():raise ValueError('Linked artifact destination forbidden')
    data,manifest=release_bytes(root)
    with output.open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    return dict(source_commit=manifest['source_commit'],migration_head=manifest['migration_head'],
                file_count=len(manifest['files']),artifact_sha256=sha256(data).hexdigest(),bytes=len(data))


def verify_bytes(data,expected_sha256):
    """Bounded source-artifact integrity check against an independently known hash.

    Does not extract or execute code. A checksum is not a signature or approval.
    """
    if (len(data)>MAX_TOTAL+2*1024**2 or not re.fullmatch('[a-f0-9]{64}',expected_sha256)
            or sha256(data).hexdigest()!=expected_sha256):raise ValueError('Release checksum mismatch')
    with zipfile.ZipFile(BytesIO(data)) as archive:
        entries=archive.infolist();names=[e.filename for e in entries]
        if (len(entries)>1000 or len(names)!=len(set(names)) or names.count('RELEASE-MANIFEST.json')!=1
                or any(e.compress_type!=zipfile.ZIP_STORED or e.file_size>MAX_FILE
                       or stat.S_IFMT(e.external_attr>>16)!=stat.S_IFREG for e in entries)):
            raise ValueError('Unexpected source archive structure')
        manifest=json.loads(archive.read('RELEASE-MANIFEST.json'))
        if (manifest.get('format')!='ohvr-source-release-v1' or manifest.get('working_tree_included') is not False
                or not re.fullmatch('[a-f0-9]{40,64}',manifest.get('source_commit',''))):
            raise ValueError('Invalid source manifest')
        files=manifest.get('files')
        if not isinstance(files,list) or len(files)!=len(entries)-1:raise ValueError('Incomplete release inventory')
        seen=set();payload={};total=0
        for item in files:
            if set(item)!= {'path','sha256','bytes'} or not allowed(item['path']) or item['path'] in seen:
                raise ValueError('Unsafe or duplicate release inventory')
            name=item['path'];content=archive.read(name);total+=len(content)
            if total>MAX_TOTAL or len(content)!=item['bytes'] or sha256(content).hexdigest()!=item['sha256']:
                raise ValueError('Release member digest/size mismatch')
            payload[name]=content;seen.add(name)
        if seen!=set(names)-{'RELEASE-MANIFEST.json'} or not REQUIRED<=seen:
            raise ValueError('Unexpected or missing release member')
        if migration_head(payload)!=manifest['migration_head']:raise ValueError('Migration head mismatch')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    operation=parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--output',type=Path)
    operation.add_argument('--verify',type=Path)
    parser.add_argument('--sha256',help='Independently trusted expected artifact digest for verification')
    args=parser.parse_args()
    try:
        if args.verify:
            if args.verify.stat().st_size>MAX_TOTAL+2*1024**2:raise ValueError('Artifact exceeds source profile')
            manifest=verify_bytes(args.verify.read_bytes(),args.sha256 or '')
            result=dict(status='integrity-verified-only',source_commit=manifest['source_commit'],migration_head=manifest['migration_head'])
        else:result=build(Path(__file__).resolve().parent.parent,args.output)
    except Exception:
        raise SystemExit('Release bundle failed safely; review committed inputs and new local destination; no existing files changed') from None
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
