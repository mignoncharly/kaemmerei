"""Document lifecycle and recovery: real restricted PostgreSQL logins when selected."""
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from hashlib import sha256
from uuid import uuid4
from zipfile import ZipFile
import json
import os
import shutil
import pytest
from sqlalchemy import select,text
from app.config import Settings
from app.documents import (ClamAVScanner,ScanResult,storage_path,validate_content,process_document,
    reconcile,disposal_eligibility)
from app.models import ContractDocument,DocumentJob,Contract,SecurityEvent
from tests.support import environment_context,login,create_contract,csrf_from,workflow_payload,scratch_directory
from tests.runtime_support import runtime_environment
from tests.scanner_support import CleanScanner


@pytest.fixture
def documents(request):
    if request.config.getoption('--database')=='postgresql':
        with runtime_environment() as r:yield r.client,r.app,r.owner
    else:
        with environment_context('sqlite') as (client,app):yield client,app,app


@pytest.fixture
def private_tmp():
    with scratch_directory('ohvr-phase5-') as directory:yield Path(directory)


class ResultScanner:
    def __init__(self,result):self.result=result
    def scan(self,data):return ScanResult(self.result,'synthetic-test-scanner')


def upload(documents,scanner=None):
    client,app,owner=documents
    if scanner is not None:app.state.document_scanner=scanner
    assert login(client,'admin').status_code==303
    record=create_contract(client)
    path=f'/contracts/{record}/documents'
    data=workflow_payload(client,path,{'csrf_token':csrf_from(client.get('/').text)})
    response=client.post(path,data=data,files={'documents':('synthetic.pdf',b'%PDF-1.4\nSynthetic content','application/pdf')},follow_redirects=False)
    assert response.status_code==303,response.text
    with owner.state.session_factory() as db:
        document=db.scalar(select(ContractDocument).where(ContractDocument.contract_id==record))
        return record,document.id,document.storage_key


@pytest.mark.parametrize('outcome',['unavailable','error','stale_database','invalid_database','infected'])
def test_non_clean_scans_never_expose_content(documents,outcome):
    record,doc,key=upload(documents,ResultScanner(outcome))
    client,app,owner=documents
    for suffix in ('','?download=1'):
        response=client.get(f'/contracts/{record}/documents/{doc}'+suffix,headers={'Range':'bytes=0-4'})
        assert response.status_code==409 and b'%PDF-' not in response.content
    with owner.state.session_factory() as db:
        d=db.get(ContractDocument,doc)
        assert d.state==('rejected' if outcome=='infected' else 'quarantined')
        assert db.get(DocumentJob,doc).state in ('retry','rejected')
        assert db.scalar(select(SecurityEvent.id).where(SecurityEvent.action=='DOCUMENT_ACCESS',SecurityEvent.outcome=='denied'))
    assert storage_path(app.state.document_storage_dir,'staging',key).exists()


def test_verified_download_ranges_and_corruption_are_checked(documents):
    record,doc,key=upload(documents,CleanScanner())
    client,app,owner=documents
    path=f'/contracts/{record}/documents/{doc}'
    response=client.get(path,headers={'Range':'bytes=0-4'})
    assert response.status_code==206 and response.content==b'%PDF-'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert response.headers['content-security-policy'].startswith('sandbox')
    assert client.get(path,headers={'Range':'bytes=999999-'}).status_code==416
    storage_path(app.state.document_storage_dir,'blobs',key).write_bytes(b'%PDF-1.4\nTampered')
    assert client.get(path).status_code==409
    with owner.state.session_factory() as db:assert reconcile(db,app.state.document_storage_dir)['mismatched']==[doc]


@pytest.mark.parametrize('point',['before_scan','after_scan','after_finalize','before_commit'])
def test_processing_crashes_are_retryable_without_exposing_uncommitted_blobs(documents,point):
    record,doc,key=upload(documents,ResultScanner('unavailable'))
    client,app,owner=documents
    def fault(at):
        if at==point:raise RuntimeError('Synthetic crash')
    with owner.state.session_factory() as db:
        with pytest.raises(RuntimeError):process_document(db,app.state.config,CleanScanner(),doc,fault=fault)
        db.rollback()
    assert client.get(f'/contracts/{record}/documents/{doc}').status_code==409
    with owner.state.session_factory() as db:
        assert process_document(db,app.state.config,CleanScanner(),doc)=='available'
        assert process_document(db,app.state.config,CleanScanner(),doc)=='available'
    assert client.get(f'/contracts/{record}/documents/{doc}').content==b'%PDF-1.4\nSynthetic content'


def container(entries):
    stream=BytesIO()
    with ZipFile(stream,'w') as z:
        for name,data in entries.items():z.writestr(name,data)
    return stream.getvalue()


@pytest.mark.parametrize('entries',[
    {'hello.txt':'Not Office'},
    {'[Content_Types].xml':'<Types/>','word/document.xml':'<document/>','word/vbaProject.bin':'macro'},
    {'[Content_Types].xml':'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///sensitive">]><Types/>','word/document.xml':'<document/>'},
    {'../escape':'x'},
    {'[Content_Types].xml':'<Types><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>','word/document.xml':'<document/>','word/_rels/document.xml.rels':'<Relationships><Relationship TargetMode="External"/></Relationships>'}
])
def test_disguised_and_active_office_containers_rejected(entries):
    with pytest.raises(ValueError):validate_content(container(entries),'.docx')


def test_valid_containers_and_nonmacro_policy():
    types='<Types><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    assert validate_content(container({'[Content_Types].xml':types,'word/document.xml':'<document/>'}),'.docx').endswith('document')
    assert validate_content(container({'mimetype':'application/vnd.oasis.opendocument.text','content.xml':'<document/>','META-INF/manifest.xml':'<manifest/>'}),'.odt').endswith('text')
    for suffix in ('.doc','.xls','.ppt','.rtf'):
        with pytest.raises(ValueError):validate_content(b'legacy active container',suffix)


@pytest.mark.parametrize('reply',[
    b'ClamAV 1.4.3',
    b'ClamAV 1.4.3/123/Mon Jan 01 00:00:00 2001',
    b'ClamAV 1.4.3/123/not-a-date',
])
def test_scanner_adapter_rejects_missing_stale_and_invalid_definitions(monkeypatch,reply):
    import subprocess
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command,0,stdout=reply)
    monkeypatch.setattr(subprocess,'run',run)
    result=ClamAVScanner(Settings(clamav_executable=Path(__file__).resolve())).scan(b'content')
    assert result.outcome in ('invalid_database','stale_database','error')
    assert len(calls)==1  # no scan may proceed without verified fresh definitions


def test_paths_and_public_storage_fail_closed(private_tmp):
    for key in ('../escape.pdf','a'*32+'.exe','C:\\escape','/etc/passwd','a'*32+'.pdf/..'):
        with pytest.raises(ValueError):storage_path(private_tmp,'blobs',key)
    with pytest.raises(ValueError):Settings(document_storage_dir=Path(__file__).resolve().parents[1]/'app'/'static'/'documents').validate()
    with pytest.raises(ValueError):Settings(document_storage_dir=Path(__file__).resolve().parents[1]/'nonexistent'/'..'/'app'/'static'/'documents').validate()


def test_interrupted_staging_removes_only_its_own_partial_file(private_tmp):
    import asyncio
    from app.documents import ensure_storage,stage_upload
    root=ensure_storage(Settings(document_storage_dir=private_tmp/'private'))
    preserved=storage_path(root,'staging',uuid4().hex+'.pdf')
    preserved.write_bytes(b'pre-existing reconciliation candidate')
    class BrokenUpload:
        filename='interrupted.pdf'
        calls=0
        closed=False
        async def read(self,size):
            self.calls+=1
            if self.calls==1:return b'%PDF-1.4\nPartial'
            raise OSError('Synthetic interrupted stream')
        async def close(self):self.closed=True
    source=BrokenUpload()
    with pytest.raises(OSError,match='Synthetic interrupted'):
        asyncio.run(stage_upload(source,root))
    assert source.closed
    assert list((root/'staging').iterdir())==[preserved]


def test_pending_document_blocks_actual_review_approval(documents):
    from tests.test_phase4 import setup_review,switch,post
    client,app,owner=documents
    record,review=setup_review(documents)
    app.state.document_scanner=ResultScanner('unavailable')
    path=f'/contracts/{record}/documents'
    data=workflow_payload(client,path,{'csrf_token':csrf_from(client.get('/').text)})
    assert client.post(path,data=data,files={'documents':('pending.pdf',b'%PDF-1.4\nPending','application/pdf')},follow_redirects=False).status_code==303
    switch(client,'pruefer')
    assert post(client,f'/contracts/{record}/reviews/{review}',status='approved',result_text='Not yet acceptable').status_code==409


def test_actual_linked_storage_is_rejected(private_tmp):
    target=private_tmp/'target';target.mkdir()
    link=private_tmp/'linked'
    try:link.symlink_to(target,target_is_directory=True)
    except OSError:pytest.skip('OS does not permit creating a symlink under this test identity')
    with pytest.raises(ValueError):Settings(document_storage_dir=link).validate()


def test_reconciliation_preserves_orphan_and_reports_missing(documents):
    record,doc,key=upload(documents,ResultScanner('unavailable'))
    _,app,owner=documents
    root=app.state.document_storage_dir
    orphan=storage_path(root,'staging',uuid4().hex+'.pdf');orphan.write_bytes(b'unclassified')
    storage_path(root,'staging',key).unlink()
    with owner.state.session_factory() as db:
        report=reconcile(db,root)
        assert report['missing']==[doc] and report['pending']==[doc]
        assert any(x['key']==orphan.name for x in report['orphans'])
    assert orphan.exists()


def test_replacement_preserves_held_predecessor_and_invalidates_content(documents):
    record,doc,key=upload(documents,CleanScanner())
    client,app,owner=documents
    root=f'/contracts/{record}/documents/{doc}'
    csrf=csrf_from(client.get('/').text)
    with owner.state.session_factory() as db:version=db.get(ContractDocument,doc).version
    data={'csrf_token':csrf,'request_id':str(uuid4()),'version':str(version)}
    assert client.post(root+'/hold',data=data,follow_redirects=False).status_code==303
    data.update(version=str(version+1),request_id=str(uuid4()))
    assert client.post(root+'/hold',data=data,follow_redirects=False).status_code==409
    data['request_id']=str(uuid4())
    assert client.post(root+'/replace',data=data,files={'document':('new.pdf',b'%PDF-1.4\nReplacement','application/pdf')},follow_redirects=False).status_code==303
    with owner.state.session_factory() as db:
        old=db.get(ContractDocument,doc)
        new=db.scalar(select(ContractDocument).where(ContractDocument.replaces_id==doc))
        assert old.state=='superseded' and old.legal_hold
        assert new.state=='available'
        assert not disposal_eligibility(old)['eligible']
        assert db.get(Contract,record).content_revision==3
    assert storage_path(app.state.document_storage_dir,'blobs',key).exists()
    assert client.get(root).status_code==409


def test_dms_correction_preserves_link_history_and_domain_policy(documents):
    client,app,owner=documents
    assert login(client,'admin').status_code==303
    record=create_contract(client)
    app.state.config=replace(app.state.config,dms_allowed_hosts=('dms.example.org',))
    path=f'/contracts/{record}/documents/link'
    data={'csrf_token':csrf_from(client.get('/').text),'request_id':str(uuid4()),'document_name':'DMS','external_url':'https://unapproved.example.org/item'}
    assert client.post(path,data=data).status_code==400
    data['external_url']='https://dms.example.org/one'
    assert client.post(path,data=data,follow_redirects=False).status_code==303
    with owner.state.session_factory() as db:
        old=db.scalar(select(ContractDocument));doc,version=old.id,old.version
    data.update(request_id=str(uuid4()),version=str(version),external_url='https://dms.example.org/two')
    assert client.post(f'/contracts/{record}/documents/{doc}/link',data=data,follow_redirects=False).status_code==303
    with owner.state.session_factory() as db:
        old=db.get(ContractDocument,doc)
        assert old.external_url.endswith('/one') and old.state=='superseded'


def test_archived_pending_jobs_cannot_publish(documents):
    record,doc,key=upload(documents,ResultScanner('unavailable'))
    client,app,owner=documents
    assert client.post(f'/contracts/{record}/archive',data={'csrf_token':csrf_from(client.get('/').text),'version':'2'},follow_redirects=False).status_code==303
    with owner.state.session_factory() as db:
        assert process_document(db,app.state.config,CleanScanner(),doc)=='archived'
        assert db.get(ContractDocument,doc).state=='quarantined'
    assert client.get(f'/contracts/{record}/documents/{doc}').status_code==409


def test_slow_scan_does_not_hold_writer_lock_and_cannot_publish_after_archive(documents):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    record,doc,key=upload(documents,ResultScanner('unavailable'))
    client,app,owner=documents
    started,released=Event(),Event()
    class PausingScanner:
        def scan(self,data):
            started.set()
            assert released.wait(timeout=15)
            return ScanResult('clean','synthetic-pausing-scanner')
    def worker():
        with owner.state.session_factory() as db:
            return process_document(db,app.state.config,PausingScanner(),doc)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task=pool.submit(worker)
        try:
            assert started.wait(timeout=10)
            assert client.post(f'/contracts/{record}/archive',data={'csrf_token':csrf_from(client.get('/').text),'version':'2'},follow_redirects=False).status_code==303
        finally:released.set()
        assert task.result(timeout=10)=='archived'
    with owner.state.session_factory() as db:assert db.get(ContractDocument,doc).state=='quarantined'


def test_metadata_commit_failure_leaves_classified_reconciliation_work(documents,monkeypatch):
    from app.models import Revision
    from sqlalchemy.orm import Session
    client,app,owner=documents
    assert login(client,'admin').status_code==303
    record=create_contract(client)
    original=Session.commit
    def fail_commit(session):
        if any(isinstance(row,Revision) and row.action=='document_uploaded' for row in session.new):
            raise RuntimeError('Synthetic metadata commit failure')
        return original(session)
    monkeypatch.setattr(Session,'commit',fail_commit)
    path=f'/contracts/{record}/documents'
    data=workflow_payload(client,path,{'csrf_token':csrf_from(client.get('/').text)})
    with pytest.raises(RuntimeError,match='Synthetic metadata'):
        client.post(path,data=data,files={'documents':('new.pdf',b'%PDF-1.4\nUncommitted','application/pdf')})
    with owner.state.session_factory() as db:
        assert db.scalar(select(ContractDocument.id)) is None
        report=reconcile(db,app.state.document_storage_dir)
        assert len(report['orphans'])==1 and report['orphans'][0]['area']=='staging'


def test_consistent_metadata_and_blob_restore_retains_hash_and_authorization(documents,request):
    from tests.backup_support import restored_fixture
    from app.main import create_app
    from fastapi.testclient import TestClient
    from app.security import COOKIE_NAME
    record,doc,key=upload(documents,CleanScanner())
    _,app,owner=documents
    with restored_fixture(owner,request.config.getoption('--database')) as (database,storage):
        restored=create_app(Settings(database_url=database,document_storage_dir=storage))
        try:
            with TestClient(restored) as client:
                assert login(client,'admin').status_code==303
                assert client.get(f'/contracts/{record}/documents/{doc}').content==b'%PDF-1.4\nSynthetic content'
                with restored.state.session_factory() as db:
                    d=db.get(ContractDocument,doc)
                    assert d.sha256==sha256(storage_path(storage,'blobs',key).read_bytes()).hexdigest()
                    assert reconcile(db,storage)['missing']==[]
                client.post('/logout',data={'csrf_token':csrf_from(client.get('/').text)})
                assert login(client,'bau').status_code==303
                assert client.get(f'/contracts/{record}/documents/{doc}').status_code==404
        finally:restored.state.engine.dispose()


def test_real_clamav_engine_with_current_official_database():
    executable=os.getenv('CLAMAV_EXECUTABLE')
    if not executable:
        if os.getenv('REQUIRE_REAL_CLAMAV')=='1':pytest.fail('Real ClamAV scanner is required')
        pytest.skip('ClamAV not installed/configured locally; authoritative scanner CI runs this test')
    settings=Settings(clamav_executable=Path(executable),clamav_database_dir=Path(os.environ['CLAMAV_DATABASE_DIR']) if os.getenv('CLAMAV_DATABASE_DIR') else None)
    scanner=ClamAVScanner(settings)
    clean=scanner.scan(b'Synthetic clean text document')
    sample=b''.join((b'X5O!P%@AP[4',b'\\PZX54(P^)7CC)7}$',b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE!',b'$H+H*'))
    detected=scanner.scan(sample)
    assert clean.outcome=='clean',clean
    assert detected.outcome=='infected',detected
    report={'clean':clean.outcome,'infected':detected.outcome,'scanner_version':clean.version,'database_freshness_enforced':True}
    Path('.verification').mkdir(exist_ok=True)
    Path('.verification/phase5-scanner.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
