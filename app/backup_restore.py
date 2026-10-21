"""Authenticate and prepare a new private restore bundle; never import a database.

The operator must supply an independently trusted signing public key. Database
import is deliberately separate: only the test harness imports into a positively
identified newly created database. A successful preparation is not a deployment.
"""
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
from uuid import uuid4

from app.backup import MAX_DUMP,MAX_FILES,RESERVE,_local
from app.backup_crypto import MAX_ARCHIVE,decrypt_file,validate_age,verify_receipt
from app.documents import KEY,MAX_BYTES,validate_storage_setting,verify_private_acl

MAX_MANIFEST=32*1024**2


def _manifest(data,metadata):
    manifest=json.loads(data)
    if set(manifest)!={'format','database','files'} or manifest['format']!='ohvr-backup-v1':
        raise ValueError('Unsupported restore manifest')
    database=manifest['database']
    if (set(database)!={'name','schema_head','server_major','sha256','size'}
            or database['schema_head']!=metadata['schema_head']
            or not isinstance(database['name'],str) or not 1<=len(database['name'])<=63
            or type(database['server_major']) is not int or not 15<=database['server_major']<=99):
        raise ValueError('Invalid restore database metadata')
    files=manifest['files']
    if not isinstance(files,list) or len(files)!=metadata['file_count'] or len(files)>MAX_FILES:
        raise ValueError('Invalid restore file inventory')
    expected={'database.dump':database}
    for item in files:
        if (set(item)!={'area','key','sha256','size','member'}
                or item['area'] not in ('legacy','staging','blobs')
                or not isinstance(item['key'],str) or not KEY.fullmatch(item['key'])
                or item['member']!=f"documents/{item['area']}/{item['key']}"
                or item['member'] in expected):
            raise ValueError('Unsafe or duplicate restore member')
        expected[item['member']]=item
    total=0
    for member,item in expected.items():
        cap=MAX_DUMP if member=='database.dump' else MAX_BYTES
        if (type(item['size']) is not int or not 0<=item['size']<=cap
                or not isinstance(item['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',item['sha256'])):
            raise ValueError('Invalid bounded restore member')
        total+=item['size']
    if total>MAX_ARCHIVE:raise ValueError('Restore inventory exceeds total profile')
    return manifest,expected,total


def prepare_restore(receipt,verifier,identity,directory,age_executable,age_sha256,*,seconds=1800,production=False):
    """Only write a fresh UUID child after receipt/ciphertext authentication.

    A failed private partial bundle is retained and has no ready.json marker.
    Do not use any extracted file until this function has returned successfully.
    No caller supplied existing destination file is overwritten or deleted.
    """
    directory=_local(Path(directory));validate_storage_setting(directory)
    if not directory.is_dir():raise ValueError('Provision a separate private recovery directory')
    for parent in (directory,*directory.parents):
        if (parent/'PG_VERSION').exists():raise ValueError('Recovery must never write inside a PostgreSQL cluster')
    for path in (receipt,verifier,identity,age_executable):_local(Path(path))
    if production:
        for path in (directory,identity,identity.parent):verify_private_acl(path)
    metadata,encrypted=verify_receipt(receipt,verifier)
    if directory==receipt.parent or directory.is_relative_to(receipt.parent):
        raise ValueError('Recovery directory must be separate from the immutable backup')
    validate_age(age_executable,age_sha256)
    if shutil.disk_usage(directory).free<metadata['ciphertext_bytes']*2+RESERVE:
        raise ValueError('Insufficient recovery capacity')
    nonce=uuid4().hex;job=directory/('restore-'+nonce)
    job.mkdir(mode=0o777 if os.name=='nt' else 0o700)
    marker=job/'stage.json'
    marker.write_text(json.dumps({'format':'ohvr-restore-stage-v1','id':nonce}),encoding='ascii')
    archive_path=job/'authenticated.tar'
    decrypt_file(age_executable,identity,encrypted,archive_path,seconds=seconds,
        expected=(metadata['ciphertext_sha256'],metadata['ciphertext_bytes']))
    # age success authenticates the complete stream before any tar parsing.
    # Never use extractall: type, exact member name, order, size and hash are checked.
    with archive_path.open('rb') as stream,tarfile.open(fileobj=stream,mode='r|') as archive:
        first=archive.next()
        if (first is None or first.name!='manifest.json' or not first.isreg()
                or first.pax_headers or not 0<first.size<=MAX_MANIFEST):
            raise ValueError('A bounded regular manifest must be the first restore member')
        with archive.extractfile(first) as source:
            data=source.read(MAX_MANIFEST+1)
        manifest,expected,total=_manifest(data,metadata)
        if shutil.disk_usage(job).free<total+RESERVE:raise ValueError('Insufficient extracted recovery capacity')
        storage=job/'documents';storage.mkdir()
        for area in ('staging','blobs'):(storage/area).mkdir()
        seen=set()
        # archive.next() advances the streaming parser past the first member.
        while entry:=archive.next():
            item=expected.get(entry.name)
            if (item is None or entry.name in seen or not entry.isreg() or entry.pax_headers
                    or entry.size!=item['size']):
                raise ValueError('Unexpected, unsafe, duplicate or oversized restore member')
            if entry.name=='database.dump':destination=job/'database.dump'
            else:
                destination=storage/item['key'] if item['area']=='legacy' else storage/item['area']/item['key']
            digest=sha256();size=0
            with archive.extractfile(entry) as source,destination.open('xb') as output:
                while chunk:=source.read(1024*1024):
                    size+=len(chunk)
                    if size>item['size']:raise ValueError('Restore member exceeded declared size')
                    digest.update(chunk);output.write(chunk)
                output.flush();os.fsync(output.fileno())
            if (size,digest.hexdigest())!=(item['size'],item['sha256']):
                raise ValueError('Restore member hash or size mismatch')
            seen.add(entry.name)
        if seen!=set(expected):raise ValueError('Restore archive is missing inventory members')
    # Only our identified staging archive is removed. Plain dump/document bundle
    # remains private for a separately reviewed import into a NEW empty target.
    if (job.resolve().parent!=directory or job.name!='restore-'+nonce
            or json.loads(marker.read_text(encoding='ascii'))!={'format':'ohvr-restore-stage-v1','id':nonce}):
        raise ValueError('Recovery staging identity changed')
    _local(archive_path);archive_path.unlink()
    manifest_path=job/'manifest.json'
    with manifest_path.open('xb') as output:output.write(data)
    result=dict(format='ohvr-restore-ready-v1',schema_head=metadata['schema_head'],
                file_count=metadata['file_count'],verified_at=datetime.now(timezone.utc).isoformat())
    with (job/'ready.json').open('x',encoding='utf-8') as output:
        json.dump(result,output);output.write('\n');output.flush();os.fsync(output.fileno())
    return job
