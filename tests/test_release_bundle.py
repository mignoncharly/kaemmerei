"""Source-only artifact tests; synthetic Git repositories, no deployment."""
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
import subprocess
import zipfile

import pytest
from scripts.build_release import REQUIRED,allowed,build,migration_head,release_bytes,verify_bytes
from tests.support import scratch_directory


def git(root,*args,input=None):
    return subprocess.run(['git','-C',str(root),*args],input=input,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,check=True,timeout=20).stdout


def commit(root):
    git(root,'-c','user.name=Synthetic Release Test','-c','user.email=test@example.invalid',
        '-c','commit.gpgsign=false','commit','-m','synthetic')


@pytest.fixture
def source():
    with scratch_directory('release-source-') as directory:
        root=Path(directory)/'repo';root.mkdir();git(root,'init')
        for name in REQUIRED|{'app/config.py','app/static/api-v2.schema.json','.env.example','README.md',
                'data/private.sqlite3','.env','.venv/private.py','documents/private.pdf','key.pem','cache.whl','deploy/windows/real.local.json'}:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'Synthetic source\n')
        migration=root/'alembic/versions/0001_initial.py';migration.parent.mkdir()
        migration.write_text("revision='0001_initial'\ndown_revision=None\n",encoding='utf-8')
        git(root,'add','--all');commit(root)
        try:yield root
        finally:
            # Git sets its own objects read-only on Windows. Clear only that
            # attribute on files inside THIS UUID synthetic repository before
            # the existing guarded scratch context removes it. No ACL changes.
            if root.resolve().parent!=Path(directory).resolve():raise RuntimeError('Fixture identity changed')
            for path in (root/'.git').rglob('*'):
                if path.is_symlink() or path.is_junction():raise RuntimeError('Unexpected linked fixture object')
                if path.is_file() and os.name=='nt':path.chmod(stat.S_IREAD|stat.S_IWRITE)


def test_release_is_byte_repeatable_manifested_and_uses_only_committed_allowlist(source):
    first,manifest=release_bytes(source)
    assert verify_bytes(first,sha256(first).hexdigest())==manifest
    with pytest.raises(ValueError,match='checksum'):verify_bytes(first,'0'*64)
    (source/'app/config.py').write_bytes(b'UNCOMMITTED LOCAL CHANGE')
    (source/'app/new-local.py').write_bytes(b'UNTRACKED LOCAL CHANGE')
    second,again=release_bytes(source)
    assert first==second and manifest==again
    assert manifest['migration_head']=='0001_initial' and not manifest['working_tree_included']
    with zipfile.ZipFile(BytesIO(first)) as archive:
        names=set(archive.namelist())
        assert {'app/main.py','requirements.lock','.env.example','RELEASE-MANIFEST.json'}<=names
        assert not names&{'data/private.sqlite3','.env','.venv/private.py','documents/private.pdf','key.pem','cache.whl','deploy/windows/real.local.json','app/new-local.py'}
        assert archive.read('app/config.py')==b'Synthetic source\n'
        metadata=json.loads(archive.read('RELEASE-MANIFEST.json'))
        assert {entry['path'] for entry in metadata['files']}==names-{'RELEASE-MANIFEST.json'}
        for entry in metadata['files']:
            data=archive.read(entry['path'])
            assert len(data)==entry['bytes'] and sha256(data).hexdigest()==entry['sha256']
    assert (source/'app/config.py').read_bytes()==b'UNCOMMITTED LOCAL CHANGE'


def test_release_writes_only_new_file_and_refuses_collision(source):
    output=source.parent/'release.zip'
    result=build(source,output)
    original=output.read_bytes()
    assert result['artifact_sha256']==sha256(original).hexdigest()
    with pytest.raises(FileExistsError):build(source,output)
    assert output.read_bytes()==original
    with pytest.raises(ValueError):build(source,Path('relative.zip'))


def test_git_link_object_is_refused_without_needing_windows_symlink_privileges(source):
    oid=git(source,'hash-object','-w','--stdin',input=b'../data/private.sqlite3').decode().strip()
    git(source,'update-index','--add','--cacheinfo','120000,'+oid+',app/link.py');commit(source)
    with pytest.raises(ValueError,match='Linked/submodule'):release_bytes(source)


@pytest.mark.parametrize('name',['app/private.pem','app/data/private.txt','alembic/credentials.json'])
def test_unclassified_runtime_object_fails_closed(source,name):
    path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic secret')
    git(source,'add','--all');commit(source)
    with pytest.raises(ValueError,match='Unclassified'):release_bytes(source)


@pytest.mark.parametrize('name',['../app/main.py','/app/main.py','app/../main.py','app\\main.py',
    'data/backup.dump','.env','requirements-dev.txt','.verification/secret','deploy/windows/real.local.json'])
def test_unsafe_or_non_release_paths_are_excluded(name):assert not allowed(name)


def test_migration_graph_rejects_missing_parent_and_branch():
    for files in [
        {'alembic/versions/a.py':b"revision='a'\ndown_revision='missing'"},
        {'alembic/versions/a.py':b"revision='a'\ndown_revision=None",'alembic/versions/b.py':b"revision='b'\ndown_revision=None"}]:
        with pytest.raises(ValueError):migration_head(files)


def test_correct_outer_hash_does_not_hide_unmanifested_extra_file(source):
    data,_=release_bytes(source);buffer=BytesIO(data)
    with zipfile.ZipFile(buffer,'a') as archive:
        info=zipfile.ZipInfo('extra.txt');info.create_system=3;info.external_attr=0o100644<<16
        archive.writestr(info,b'synthetic extra')
    changed=buffer.getvalue()
    with pytest.raises(ValueError,match='inventory'):verify_bytes(changed,sha256(changed).hexdigest())


def test_runtime_smoke_child_receives_no_database_or_recovery_credentials(source,monkeypatch):
    from scripts import verify_release_runtime as smoke
    data,_=release_bytes(source);archive=source.parent/'synthetic.zip';archive.write_bytes(data)
    captured={}
    def run(args,**kwargs):
        captured.update(args=args,**kwargs)
        return SimpleNamespace(returncode=0,stdout=json.dumps(dict(status='packaged-runtime-smoke-passed',
            migration_head='0001_initial',database='in-memory SQLite only')).encode())
    monkeypatch.setenv('PGPASSWORD','SYNTHETIC_NEVER_PASS')
    monkeypatch.setenv('MIGRATION_DATABASE_URL','SYNTHETIC_NEVER_PASS')
    monkeypatch.setenv('MFA_KEY_FILE','SYNTHETIC_NEVER_PASS')
    monkeypatch.setattr(smoke.subprocess,'run',run)
    result=smoke.verify(archive,sha256(data).hexdigest())
    assert result['status']=='packaged-runtime-smoke-passed'
    assert captured['env']['DATABASE_URL']=='sqlite:///:memory:'
    assert captured['env']['APP_ENV']=='development'
    assert not {'PGPASSWORD','PGPASSFILE','MIGRATION_DATABASE_URL','MFA_KEY_FILE'}&captured['env'].keys()
    assert captured['args'][1]=='-I' and captured['timeout']==120


def test_runtime_lock_matches_provenance_and_direct_requirements():
    import re
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    root=Path(__file__).resolve().parent.parent
    raw=(root/'requirements.lock').read_bytes()
    provenance=json.loads((root/'docs/evidence/phase9-runtime-lock-provenance.json').read_text(encoding='utf-8'))
    assert sha256(raw).hexdigest()==provenance['requirements_lock_sha256']
    pins={}
    for line in raw.decode('utf-8').replace('\\\n',' ').splitlines():
        if not line.strip() or line.startswith('#'):continue
        requirement=Requirement(line.split('--hash')[0].strip())
        hashes=re.findall(r'--hash=sha256:([a-f0-9]{64})',line)
        assert hashes and len(requirement.specifier)==1 and next(iter(requirement.specifier)).operator=='=='
        pins[canonicalize_name(requirement.name)]=next(iter(requirement.specifier)).version
    assert pins=={p['name']:p['version'] for p in provenance['packages']}
    for line in (root/'requirements.txt').read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#'):
            requirement=Requirement(line)
            assert pins[canonicalize_name(requirement.name)] in requirement.specifier


def test_hosted_release_workflow_parses_and_requires_both_platforms():
    import yaml
    root=Path(__file__).resolve().parent.parent
    # Regression for the actual pre-job failure: ': ' in a plain YAML scalar.
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load('run: python -m pip install --only-binary=:all: -r requirements.lock')
    workflow=yaml.safe_load((root/'.github/workflows/phase1-verification.yml').read_text(encoding='utf-8'))
    jobs=workflow['jobs'];release=jobs['locked-release']
    assert release['strategy']['matrix']['os']==['ubuntu-24.04','windows-latest']
    installs=[step.get('run','') for step in release['steps']]
    assert any('--require-hashes --only-binary=:all: -r requirements.lock' in command for command in installs)
    assert jobs['release-reproducibility']['needs']=='locked-release'
