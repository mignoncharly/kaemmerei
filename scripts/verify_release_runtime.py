"""Run an explicitly selected, hash-verified own release in a fresh scratch bundle.

This executes the selected application code. Use an independently trusted hash
of a reviewed source build. No production settings/credentials enter the child;
its only database is in-memory SQLite. This is not PostgreSQL/TLS acceptance.
"""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import zipfile

from scripts.build_release import MAX_TOTAL,verify_bytes

SMOKE=r'''
import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from sqlalchemy import text
from app.config import Settings
from app.main import create_app
from app.migrations import upgrade_connection
settings=Settings(database_url='sqlite:///:memory:',document_storage_dir=Path(sys.argv[1])/'synthetic-documents')
app=create_app(settings)
with app.state.engine.begin() as connection:
    upgrade_connection(connection)
    assert connection.scalar(text('SELECT version_num FROM alembic_version'))==sys.argv[2]
    assert connection.scalar(text('SELECT count(*) FROM users'))==0
async def check():
    async with app.router.lifespan_context(app):
        assert len(app.routes)>20
asyncio.run(check())
app.state.engine.dispose()
print(json.dumps(dict(status='packaged-runtime-smoke-passed',migration_head=sys.argv[2],database='in-memory SQLite only')))
'''


def verify(archive_path,expected_sha256):
    if archive_path.stat().st_size>MAX_TOTAL+2*1024**2:raise ValueError('Oversized source archive')
    data=archive_path.read_bytes();manifest=verify_bytes(data,expected_sha256)
    scratch=Path(__file__).resolve().parent.parent/'.verification'
    scratch.mkdir(exist_ok=True)
    for parent in (scratch,*scratch.parents):
        if parent.is_symlink() or parent.is_junction():raise ValueError('Linked smoke workspace forbidden')
    root=scratch/('release-smoke-'+uuid4().hex);root.mkdir()
    # verify_bytes checked every exact regular member/path/hash before extraction.
    with zipfile.ZipFile(BytesIO(data)) as archive:
        for info in archive.infolist():
            destination=root.joinpath(*info.filename.split('/'))
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('xb') as output:output.write(archive.read(info))
    env={key:value for key,value in os.environ.items() if key.upper() in
         ('SYSTEMROOT','WINDIR','TEMP','TMP','PATH','LANG','LC_ALL')}
    env.update(APP_ENV='development',DATABASE_URL='sqlite:///:memory:')
    result=subprocess.run([sys.executable,'-I','-c',SMOKE,str(root),manifest['migration_head']],
        cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=120)
    if result.returncode:raise ValueError('Packaged runtime smoke failed')
    actual=json.loads(result.stdout)
    if (actual.get('status')!='packaged-runtime-smoke-passed'
            or actual.get('migration_head')!=manifest['migration_head']
            or actual.get('database')!='in-memory SQLite only'):raise ValueError('Unexpected smoke result')
    return dict(**actual,source_commit=manifest['source_commit'],artifact_sha256=expected_sha256)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--sha256',required=True)
    args=parser.parse_args()
    try:result=verify(args.archive,args.sha256)
    except Exception:
        raise SystemExit('Release runtime verification failed; inspect own isolated source bundle; no production database used') from None
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
