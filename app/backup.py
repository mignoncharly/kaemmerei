"""Consistent, encrypted owner-operated backups; no production restore/import.

All application/domain writers must honor the existing identity guard. A backup
holds it across the exported PostgreSQL snapshot and private file capture. Use a
reviewed maintenance window: reads continue, mutations may receive busy errors.
No retention deletion, source file deletion, cluster change or service control.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime,timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tarfile
from uuid import uuid4

from sqlalchemy import select,text

from app.backup_crypto import (encrypt_stream,file_digest,signed_receipt,small_file,
                               validate_age,_tool_env)
from app.db import make_session_factory
from app.documents import KEY,MAX_BYTES,reject_links,validate_storage_setting,verify_private_acl
from app.identity_service import lock_identities
from app.migrations import migration_head
from app.models import ContractDocument

BACKUP_LOCK=724931823
MAX_FILES=100000
MAX_DUMP=20*1024**3
RESERVE=256*1024**2


@dataclass(frozen=True)
class BackupOptions:
    directory:Path
    age_executable:Path
    age_sha256:str
    recipients_file:Path
    signing_key:Path
    pg_dump:Path
    seconds:int=1800
    production:bool=False


def _local(path):
    if not path.is_absolute() or (os.name=='nt' and str(path).startswith('\\\\')):
        raise ValueError('Explicit local operation paths required')
    reject_links(path)
    return path.resolve()


def _pg_environment(url,seconds):
    env=_tool_env()
    if os.environ.get('PGPASSFILE'):env['PGPASSFILE']=os.environ['PGPASSFILE']
    env.update(PGHOST=url.host or 'localhost',PGPORT=str(url.port or 5432),PGUSER=url.username or '',
               PGDATABASE=url.database,PGCONNECT_TIMEOUT='5',
               PGOPTIONS=f'-c statement_timeout={seconds*1000} -c lock_timeout=5000')
    if url.password:env['PGPASSWORD']=url.password
    for key,var in (('sslmode','PGSSLMODE'),('sslrootcert','PGSSLROOTCERT'),
                    ('sslcert','PGSSLCERT'),('sslkey','PGSSLKEY')):
        if url.query.get(key):env[var]=url.query[key]
    return env


@contextmanager
def _operator_lock(engine,database):
    # Validate before creating directories, starting tools or acquiring row locks.
    if (engine.dialect.name!='postgresql' or not database or
            database in ('postgres','template0','template1') or engine.url.database!=database):
        raise ValueError('Explicit named PostgreSQL application database required; no default/control database')
    with engine.connect() as connection:
        actual=connection.execute(text("""SELECT current_database(),current_user,r.rolsuper,r.rolbypassrls,
            (SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='ohvr_security')
            FROM pg_roles r WHERE rolname=current_user""")).one()
        if actual[0]!=database or actual[1]!=actual[4] or actual[2] or actual[3]:
            raise ValueError('Direct non-superuser application schema owner required')
        acquired=connection.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':BACKUP_LOCK})
        connection.commit()
        if not acquired:raise ValueError('Another backup is already active')
        try:yield
        finally:
            connection.rollback()
            if not connection.scalar(text('SELECT pg_advisory_unlock(:key)'),{'key':BACKUP_LOCK}):
                raise RuntimeError('Backup operator lock was lost')
            connection.commit()


def _files(root):
    validate_storage_setting(root)
    root=_local(root)
    if not root.is_dir():raise ValueError('Private source storage is missing')
    result=[]
    for area in ('legacy','staging','blobs'):
        directory=root if area=='legacy' else root/area
        reject_links(directory)
        if not directory.is_dir():raise ValueError('Required source storage area is missing')
        for path in sorted(directory.iterdir()):
            if area=='legacy' and path.name in ('staging','blobs'):continue
            reject_links(path)
            if not path.is_file() or not KEY.fullmatch(path.name):
                raise ValueError('Unclassified storage object; reconcile without deletion before backup')
            digest,size=file_digest(path,limit=MAX_BYTES)
            result.append(dict(path=path,area=area,key=path.name,sha256=digest,size=size,
                               member=f'documents/{area}/{path.name}'))
            if len(result)>MAX_FILES:raise ValueError('Private file inventory exceeds backup profile')
    return result


def _add_file(archive,member,path,size):
    reject_links(path)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size!=size:
            raise ValueError('Backup source changed or is not a regular private file')
        entry=tarfile.TarInfo(member);entry.size=size;entry.mode=0o600
        archive.addfile(entry,stream)
        after=os.fstat(stream.fileno())
        if (after.st_size,after.st_mtime_ns)!=(info.st_size,info.st_mtime_ns):
            raise ValueError('Backup source changed while archiving')


def create_backup(engine,settings,options,*,database):
    if not 30<=options.seconds<=7200:raise ValueError('Bounded backup deadline required')
    if (engine.dialect.name!='postgresql' or not database or
            database in ('postgres','template0','template1') or engine.url.database!=database):
        raise ValueError('Explicit named PostgreSQL application database required; no default/control database')
    if options.production or settings.production:
        from app.config import validate_database_tls
        validate_database_tls(engine.url.render_as_string(hide_password=False))
    directory=_local(options.directory)
    validate_storage_setting(directory)
    storage=_local(settings.document_storage_dir)
    if not directory.is_dir():raise ValueError('Provision the private backup directory separately')
    if directory==storage or directory.is_relative_to(storage) or storage.is_relative_to(directory):
        raise ValueError('Backup and live document directories must be separate')
    for parent in (directory,*directory.parents):
        if (parent/'PG_VERSION').exists():raise ValueError('Backup destination must never be inside a PostgreSQL cluster')
    for path in (options.recipients_file,options.signing_key,options.age_executable,options.pg_dump):_local(path)
    if options.signing_key.resolve().is_relative_to(directory):
        raise ValueError('Backup signing key must be in separate protected custody')
    validate_age(options.age_executable,options.age_sha256)
    if options.production or settings.production:
        verify_private_acl(directory);verify_private_acl(options.signing_key);verify_private_acl(options.signing_key.parent)
    with _operator_lock(engine,database):
        with make_session_factory(engine)() as db:
            created=datetime.now(timezone.utc).isoformat()
            db.connection(execution_options={'isolation_level':'REPEATABLE READ'})
            lock_identities(db)
            try:
                schema=db.scalar(text('SELECT version_num FROM alembic_version'))
                if schema!=migration_head():raise ValueError('Review current migrations and inventory before backup')
                server_version=int(db.scalar(text('SHOW server_version_num')))
                major=server_version//10000
                result=subprocess.run([str(options.pg_dump),'--version'],capture_output=True,
                                      env=_tool_env(),timeout=10,check=True)
                if not re.search(rb'\b'+str(major).encode()+rb'\.',result.stdout):
                    raise ValueError('Matching PostgreSQL client major required')
                if options.production or settings.production:
                    from app.server_security import validate_server_version,validate_pg_dump_version
                    validate_server_version(server_version)
                    validate_pg_dump_version(result.stdout)
                snapshot=db.scalar(text('SELECT pg_export_snapshot()'))
                files=_files(storage)
                by_key={}
                for item in files:by_key.setdefault(item['key'],[]).append(item)
                expected=db.execute(select(ContractDocument.storage_key,ContractDocument.sha256,ContractDocument.state)
                                    .where(ContractDocument.storage_key.is_not(None))).all()
                for key,digest,state in expected:
                    candidates=by_key.get(key,[])
                    if (not candidates or (state in ('available','superseded') and not any(i['area']=='blobs' for i in candidates))
                            or (digest and any(i['sha256']!=digest for i in candidates))):
                        raise ValueError('Source storage is missing or differs from database; backup not healthy')
                estimated=int(db.scalar(text('SELECT pg_database_size(current_database())')))
                if estimated>MAX_DUMP or shutil.disk_usage(directory).free<estimated*2+sum(i['size'] for i in files)+RESERVE:
                    raise ValueError('Insufficient private capacity or database exceeds backup profile')
                nonce=uuid4().hex;job=directory/('backup-'+nonce)
                job.mkdir(mode=0o777 if os.name=='nt' else 0o700)
                marker=job/'stage.json'
                marker.write_text(json.dumps({'format':'ohvr-backup-stage-v1','id':nonce}),encoding='ascii')
                dump=job/'database.dump'
                with dump.open('xb') as output:
                    subprocess.run([str(options.pg_dump),'--format=custom','--no-owner','--no-privileges',
                        '--enable-row-security','--snapshot='+snapshot],stdout=output,stderr=subprocess.DEVNULL,
                        env=_pg_environment(engine.url,options.seconds),timeout=options.seconds,check=True)
                    output.flush();os.fsync(output.fileno())
                dump_hash,dump_size=file_digest(dump,limit=MAX_DUMP)
                if dump_size<5:raise ValueError('Invalid database dump')
                manifest=dict(format='ohvr-backup-v1',database=dict(name=database,schema_head=schema,
                    server_major=major,sha256=dump_hash,size=dump_size),
                    files=[{k:v for k,v in item.items() if k!='path'} for item in files])
                data=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode('utf-8')
                if len(data)>32*1024*1024:raise ValueError('Backup manifest exceeds profile')
                artifact=job/('bundle-'+nonce+'.tar.age')
                def write(stream):
                    with tarfile.open(fileobj=stream,mode='w|',format=tarfile.USTAR_FORMAT) as archive:
                        entry=tarfile.TarInfo('manifest.json');entry.size=len(data);entry.mode=0o600
                        archive.addfile(entry,BytesIO(data))
                        _add_file(archive,'database.dump',dump,dump_size)
                        for item in files:_add_file(archive,item['member'],item['path'],item['size'])
                encrypt_stream(options.age_executable,options.recipients_file,artifact,write,seconds=options.seconds)
                encrypted_hash,encrypted_size=file_digest(artifact)
                # Only remove our positively marked single plaintext staging file.
                # On failure leave private artifacts for local inspection; never
                # recursively remove source, cluster or arbitrary backup paths.
                if (job.resolve().parent!=directory or job.name!='backup-'+nonce
                        or json.loads(small_file(marker))!={'format':'ohvr-backup-stage-v1','id':nonce}):
                    raise ValueError('Staging identity changed; plaintext cleanup refused')
                reject_links(dump)
                if file_digest(dump,limit=MAX_DUMP)!=(dump_hash,dump_size):raise ValueError('Staging dump changed')
                dump.unlink()
                metadata=dict(format='ohvr-backup-v1',created_at=created,
                    finished_at=datetime.now(timezone.utc).isoformat(),schema_head=schema,
                    ciphertext_file=artifact.name,ciphertext_sha256=encrypted_hash,
                    ciphertext_bytes=encrypted_size,file_count=len(files))
                receipt=signed_receipt(metadata,options.signing_key)
                with (job/'receipt.json').open('x',encoding='utf-8') as output:
                    json.dump(receipt,output,sort_keys=True);output.write('\n');output.flush();os.fsync(output.fileno())
                return dict(job=job.name,receipt='receipt.json',status='complete',file_count=len(files))
            finally:
                db.rollback()  # Release writer guard; no business-data mutation.
