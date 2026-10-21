"""Encrypted/signed recovery using synthetic data and positively guarded PG DBs."""
from dataclasses import replace
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from time import monotonic
from uuid import uuid4

from cryptography.fernet import Fernet
import pytest
from sqlalchemy import select,text
from sqlalchemy.engine import make_url

from app.backup import BACKUP_LOCK,BackupOptions,_pg_environment,create_backup
from app.backup_crypto import encrypt_stream,file_digest,signed_receipt,verify_receipt
from app.backup_restore import prepare_restore
from app.db import make_engine,make_session_factory
from app.db_roles import configure_runtime_roles
from app.mfa_codec import SeedCipher
from app.models import Contract,ContractDocument,Revision,MfaCredential,User
from tests.support import disposable_database,environment_context,scratch_directory
from tests.test_backup_crypto import backup_keys
from tests.test_phase5 import upload
from tests.runtime_support import runtime_environment
from tests.support import login,create_contract
from fastapi.testclient import TestClient
from app.main import create_app
from unittest.mock import patch


def pg_bin(engine):
    with engine.connect() as connection:major=int(connection.scalar(text('SHOW server_version_num')))//10000
    binary='pg_dump.exe' if os.name=='nt' else 'pg_dump'
    candidates=[Path(os.getenv('OHVR_NATIVE_BIN','__not_configured__')),
        Path(r'C:\Program Files\PostgreSQL')/str(major)/'bin',Path('/usr/lib/postgresql')/str(major)/'bin']
    result=next((path for path in candidates if (path/binary).is_file()),None)
    if result is None and shutil.which(binary):result=Path(shutil.which(binary)).parent
    if result is None:pytest.fail('Matching PostgreSQL backup/restore tools required')
    return result


@pytest.mark.postgresql
def test_actual_encrypted_consistent_backup_and_guarded_new_database_restore(backup_keys,request):
    if request.config.getoption('--database')!='postgresql':pytest.skip('Actual isolated PostgreSQL backup required')
    keys=backup_keys
    with runtime_environment() as runtime:
        client,owner=runtime.client,runtime.owner
        record,document,key=upload((client,owner,owner))
        other_record=create_contract(client,department_id='2')
        mfa_file=keys.root/'mfa.json'
        mfa_file.write_text(json.dumps([Fernet.generate_key().decode()]),encoding='ascii')
        cipher=SeedCipher(mfa_file);seed='JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'
        with owner.state.session_factory() as db:
            user=db.scalar(select(User).where(User.username=='admin'))
            user_id=user.id;encrypted_seed=cipher.encrypt(user_id,seed)
            db.add(MfaCredential(user_id=user_id,seed_ciphertext=encrypted_seed,enabled=True,last_step=123))
            db.commit()
            history=list(db.scalars(select(Revision.id).where(Revision.contract_id==record)))
        # A valid orphan is retained, not deleted or silently omitted.
        orphan=uuid4().hex+'.txt'
        (owner.state.document_storage_dir/'staging'/orphan).write_bytes(b'Synthetic orphan')
        directory=keys.root/'backups';directory.mkdir()
        tools=pg_bin(owner.state.engine)
        options=BackupOptions(directory,keys.executable,keys.sha256,keys.recipients,keys.signer,
            tools/('pg_dump.exe' if os.name=='nt' else 'pg_dump'),seconds=60)
        started=monotonic()
        result=create_backup(owner.state.engine,owner.state.config,options,database=owner.state.engine.url.database)
        backup_seconds=monotonic()-started
        job=directory/result['job']
        metadata,_=verify_receipt(job/'receipt.json',keys.verifier)
        assert result['status']=='complete' and metadata['file_count']==2
        assert not (job/'database.dump').exists()
        assert set(path.name for path in job.iterdir())=={'stage.json','receipt.json',metadata['ciphertext_file']}
        recovery=keys.root/'recovery';recovery.mkdir()
        started=monotonic()
        prepared=prepare_restore(job/'receipt.json',keys.verifier,keys.identity,recovery,
            keys.executable,keys.sha256,seconds=60)
        assert (prepared/'ready.json').is_file() and not (prepared/'authenticated.tar').exists()
        assert (prepared/'documents'/'staging'/orphan).read_bytes()==b'Synthetic orphan'
        with disposable_database('postgresql',prepared) as url:
            target=make_url(url)
            # This context created and positively identified a NEW empty target.
            # No --clean, cluster deletion or existing database import is offered.
            restore=tools/('pg_restore.exe' if os.name=='nt' else 'pg_restore')
            with (prepared/'database.dump').open('rb') as source:
                subprocess.run([str(restore),'--exit-on-error','--no-owner','--no-privileges','--dbname',target.database],
                    stdin=source,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    env=_pg_environment(target,60),check=True,timeout=60)
            engine=make_engine(replace(owner.state.config,database_url=url,document_storage_dir=prepared/'documents'))
            try:
                with make_session_factory(engine)() as db:
                    assert db.get(Contract,record).department_id==1
                    restored=db.get(ContractDocument,document)
                    payload=(prepared/'documents'/'blobs'/key).read_bytes()
                    assert restored.state=='available' and sha256(payload).hexdigest()==restored.sha256
                    assert list(db.scalars(select(Revision.id).where(Revision.contract_id==record)))==history
                    factor=db.get(MfaCredential,user_id)
                    assert factor.seed_ciphertext==encrypted_seed and factor.last_step==123
                    assert cipher.decrypt(user_id,factor.seed_ciphertext)==seed
                    assert db.scalar(text('SELECT count(*) FROM pg_class WHERE relname IN (\'contracts\',\'mfa_credentials\') AND relforcerowsecurity'))==2
                # Reapply explicit runtime grants on the NEW target after import,
                # then verify effective permissions using actual restricted LOGINs.
                with engine.begin() as connection:
                    configure_runtime_roles(connection,web=runtime.names['web'],integration=runtime.names['integration'],
                        maintenance=runtime.names['maintenance'],audit_owner=runtime.names['audit'])
                web=make_url(runtime.urls['web']).set(database=target.database).render_as_string(hide_password=False)
                integration=make_url(runtime.urls['integration']).set(database=target.database).render_as_string(hide_password=False)
                restored_app=create_app(replace(runtime.app.state.config,database_url=web,
                    integration_database_url=integration,document_storage_dir=prepared/'documents'))
                try:
                    with TestClient(restored_app) as restored_client:
                        assert login(restored_client,'kultur').status_code==303
                        assert restored_client.get(f'/contracts/{record}').status_code==200
                        assert restored_client.get(f'/contracts/{other_record}').status_code==404
                        response=restored_client.get(f'/contracts/{record}/documents/{document}')
                        assert response.status_code==200 and response.content==payload
                finally:
                    restored_app.state.engine.dispose();restored_app.state.integration_engine.dispose()
            finally:engine.dispose()
        restore_seconds=monotonic()-started
        # Measured tiny synthetic exercise, explicitly not a production RTO claim.
        request.node.user_properties.extend([('backup_seconds',round(backup_seconds,3)),('restore_seconds',round(restore_seconds,3))])
        assert backup_seconds<60 and restore_seconds<60
        # Guarded overlap is a failure, never a second successful backup.
        before=set(directory.iterdir())
        with owner.state.engine.connect() as held:
            held.execute(text('SELECT pg_advisory_lock(:key)'),{'key':BACKUP_LOCK});held.commit()
            try:
                with pytest.raises(ValueError,match='already active'):
                    create_backup(owner.state.engine,owner.state.config,options,database=owner.state.engine.url.database)
            finally:held.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':BACKUP_LOCK});held.commit()
        assert set(directory.iterdir())==before
        # A missing live blob must not produce another healthy receipt.
        blob=owner.state.document_storage_dir/'blobs'/key
        preserved=blob.read_bytes();blob.unlink()
        try:
            with pytest.raises(ValueError,match='Source storage'):
                create_backup(owner.state.engine,owner.state.config,options,database=owner.state.engine.url.database)
        finally:blob.write_bytes(preserved)
        assert set(directory.iterdir())==before


@pytest.mark.parametrize('name',['postgres','template0','template1','not-the-actual-database'])
def test_default_or_mismatched_backup_target_refused_before_output(environment,name):
    _,app=environment
    options=BackupOptions(Path('unused'),Path('unused'),'invalid',Path('unused'),Path('unused'),Path('unused'))
    with pytest.raises(ValueError,match='Explicit named PostgreSQL'):
        create_backup(app.state.engine,app.state.config,options,database=name)


def test_cli_restore_failure_is_redacted_and_does_not_initialize_database(capsys):
    from app.cli import main
    arguments=['ohvr','backup-prepare-restore']
    for option in ('receipt','verifier','identity','directory','age','age-sha256'):
        arguments.extend(('--'+option,'invalid-test-path'))
    with patch('sys.argv',arguments),patch('app.cli.make_engine') as engine:
        with pytest.raises(SystemExit,match='no database imported'):main()
        engine.assert_not_called()
    assert not capsys.readouterr().out


@pytest.mark.parametrize('fault',['traversal','symlink','duplicate','bad-hash','missing'])
def test_authenticated_malicious_or_incomplete_archive_never_ready(backup_keys,fault):
    keys=backup_keys
    nonce=uuid4().hex;artifact=keys.root/('bundle-'+nonce+'.tar.age')
    payload=b'PGDMP synthetic';now=datetime.now(timezone.utc).isoformat()
    manifest=dict(format='ohvr-backup-v1',database=dict(name='synthetic',schema_head='0023_human_mfa',
        server_major=18,sha256=sha256(payload).hexdigest(),size=len(payload)),files=[])
    if fault=='bad-hash':manifest['database']['sha256']='0'*64
    def write(stream):
        with tarfile.open(fileobj=stream,mode='w|',format=tarfile.USTAR_FORMAT) as archive:
            data=json.dumps(manifest).encode();entry=tarfile.TarInfo('manifest.json');entry.size=len(data)
            archive.addfile(entry,BytesIO(data))
            if fault!='missing':
                entry=tarfile.TarInfo('../outside.dump' if fault=='traversal' else 'database.dump')
                if fault=='symlink':entry.type=tarfile.SYMTYPE;entry.linkname='../../outside'
                else:entry.size=len(payload)
                archive.addfile(entry,BytesIO(payload))
                if fault=='duplicate':archive.addfile(entry,BytesIO(payload))
    encrypt_stream(keys.executable,keys.recipients,artifact,write,seconds=15)
    digest,size=file_digest(artifact)
    metadata=dict(format='ohvr-backup-v1',created_at=now,finished_at=now,schema_head='0023_human_mfa',
        ciphertext_file=artifact.name,ciphertext_sha256=digest,ciphertext_bytes=size,file_count=0)
    receipt=keys.root/'receipt.json';receipt.write_text(json.dumps(signed_receipt(metadata,keys.signer)),encoding='utf-8')
    recovery=keys.root/'recovery';recovery.mkdir()
    with pytest.raises(ValueError):
        prepare_restore(receipt,keys.verifier,keys.identity,recovery,keys.executable,keys.sha256,seconds=15)
    assert not list(recovery.rglob('ready.json')) and not (keys.root/'outside.dump').exists()
