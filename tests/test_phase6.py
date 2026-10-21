"""Reliable synchronization against SQLite and actual restricted PostgreSQL roles."""
from datetime import timedelta
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import re
import pytest
from sqlalchemy import select,text,func,event
from sqlalchemy.exc import DBAPIError
from app.models import (Contract,IntegrationToken,SyncState,SyncOutbox,SyncEvent,SyncCursor,User,Department,now_utc)
from app.security import hash_value
from tests.support import environment_context,login,create_contract,csrf_from,workflow_payload
from tests.runtime_support import runtime_environment


@pytest.fixture
def sync(request):
    if request.config.getoption('--database')=='postgresql':
        with runtime_environment() as r:yield r.client,r.app,r.owner
    else:
        with environment_context('sqlite') as (client,app):yield client,app,app


def token(sync,department=None,scopes='metadata',**values):
    _,_,owner=sync;raw='ohvr_'+uuid4().hex
    with owner.state.session_factory() as db:
        row=IntegrationToken(name='Synthetic service',token_prefix=raw[:16],token_hash=hash_value(raw),
            department_id=department,created_by_id=1,owner_user_id=1,service_owner='Synthetic owner',
            api_scopes=scopes,expires_at=now_utc()+timedelta(days=90),**values)
        db.add(row);db.commit();identifier=row.id
    return {'Authorization':'Bearer '+raw},identifier


def record(sync,department='1',title='Synthetic sync contract'):
    client,_,_=sync
    assert login(client,'admin').status_code==303
    return create_contract(client,department_id=department,designation=title)


def snapshot(client,headers,**params):
    response=client.get('/api/v2/snapshot',headers=headers,params=params)
    assert response.status_code==200
    return response.json()


def changes(client,headers,cursor,**params):
    response=client.get('/api/v2/changes',headers=headers,params={'cursor':cursor,**params})
    assert response.status_code==200
    return response.json()


def test_materialized_snapshot_pagination_and_following_changes(sync):
    client,_,owner=sync
    first,second=record(sync,title='First snapshot'),record(sync,title='Second snapshot')
    headers,_=token(sync)
    start=snapshot(client,headers,limit=1)
    assert start['next_cursor'] and not start['changes_cursor']
    with owner.state.session_factory() as db:
        db.get(Contract,second).designation='Updated after boundary';db.commit()
    last=snapshot(client,headers,cursor=start['next_cursor'],limit=1)
    assert last['data'][0]['designation']=='Second snapshot'
    assert last['changes_cursor'] and last['next_cursor'] is None
    page=changes(client,headers,last['changes_cursor'])
    assert any(e['contract_id']==second and e['operation']=='upsert' for e in page['data'])
    replay=changes(client,headers,last['changes_cursor'])
    assert replay['data']==page['data']
    assert changes(client,headers,page['next_cursor'])['data']==[]


def test_transfer_sends_minimal_removal_and_new_scope_upsert(sync):
    client,_,owner=sync;cid=record(sync)
    a,_=token(sync,1);b,_=token(sync,2)
    ca=snapshot(client,a)['changes_cursor'];cb=snapshot(client,b)['changes_cursor']
    with owner.state.session_factory() as db:
        c=db.get(Contract,cid);c.department_id=2;c.contact_identity_id=None;db.commit()
    removed=changes(client,a,ca)['data'];added=changes(client,b,cb)['data']
    assert removed and all(set(x)=={'event_id','contract_id','operation','reason'} and x['operation']=='remove' for x in removed)
    assert any(x['contract_id']==cid and x['operation']=='upsert' for x in added)
    assert client.get(f'/api/v2/contracts/{cid}',headers=a).status_code==404
    assert client.get(f'/api/v2/contracts/{cid}',headers=b).status_code==200


def test_explicit_capabilities_and_v1_cannot_bypass_them(sync):
    client,_,_=sync;cid=record(sync)
    limited,_=token(sync);legacy,_=token(sync,scopes='legacy_v1')
    body=client.get(f'/api/v2/contracts/{cid}',headers=limited).json()['data']
    assert not {'finance','tax','tasks','documents','history_url'} & body.keys()
    assert client.get('/api/v1/contracts',headers=limited).status_code==403
    assert client.get('/api/v2/snapshot',headers=legacy).status_code==403
    assert client.get('/api/v1/contracts',headers=legacy).status_code==200
    assert client.get(f'/api/v2/contracts/{cid}/history',headers=limited).status_code==403
    assert client.get(f'/api/v2/contracts/{cid}/documents/1',headers=limited).status_code==403
    all_fields,_=token(sync,scopes='metadata,finance,tax,tasks,documents,document_content,history')
    detail=client.get(f'/api/v2/contracts/{cid}',headers=all_fields)
    assert detail.status_code==200
    assert {'finance','tax','tasks','documents','reviews','decisions','history_url'}<=detail.json()['data'].keys()
    assert client.get(f'/api/v2/contracts/{cid}/history',headers=all_fields).json()['data']


def test_cursor_scope_tamper_expiry_and_retention_require_explicit_restart(sync):
    client,_,owner=sync;cid=record(sync)
    headers,identifier=token(sync,1);other,_=token(sync,1)
    cursor=snapshot(client,headers)['changes_cursor']
    assert client.get('/api/v2/changes',params={'cursor':cursor+'x'},headers=headers).status_code==400
    assert client.get('/api/v2/changes',params={'cursor':cursor},headers=other).status_code==400
    with owner.state.session_factory() as db:
        db.get(IntegrationToken,identifier).api_scopes='metadata,finance';db.commit()
    assert client.get('/api/v2/changes',params={'cursor':cursor},headers=headers).status_code==410
    cursor=snapshot(client,headers)['changes_cursor']
    with owner.state.session_factory() as db:
        row=db.get(SyncCursor,hash_value(cursor));row.expires_at=now_utc()-timedelta(seconds=1);db.commit()
    assert client.get('/api/v2/changes',params={'cursor':cursor},headers=headers).status_code==410
    cursor=snapshot(client,headers)['changes_cursor']
    with owner.state.session_factory() as db:db.get(Contract,cid).designation='Publish after old boundary';db.commit()
    changes(client,headers,cursor)
    with owner.state.session_factory() as db:
        state=db.get(SyncState,1);state.floor=state.next_seq;db.commit()
    assert client.get('/api/v2/changes',params={'cursor':cursor},headers=headers).status_code==410


@pytest.mark.parametrize('condition',['expired','revoked','owner_disabled','department_disabled'])
def test_token_suspension_is_server_enforced(sync,condition):
    client,_,owner=sync;record(sync)
    headers,identifier=token(sync,1)
    cursor=snapshot(client,headers)['changes_cursor']
    with owner.state.session_factory() as db:
        row=db.get(IntegrationToken,identifier)
        if condition=='expired':row.expires_at=now_utc()-timedelta(seconds=1)
        elif condition=='revoked':row.is_active=False;row.revoked_at=now_utc()
        elif condition=='owner_disabled':db.get(User,1).is_active=False
        else:db.get(Department,1).is_active=False
        db.commit()
    assert client.get('/api/v2/changes',params={'cursor':cursor},headers=headers).status_code==401
    assert client.get('/api/v2/snapshot',headers=headers).status_code==401
    if condition=='owner_disabled':
        with owner.state.session_factory() as db:db.get(User,1).is_active=True;db.commit()
        assert client.get('/api/v2/changes',params={'cursor':cursor},headers=headers).status_code==410


def test_rollback_never_publishes_and_concurrent_publication_is_idempotent(sync):
    client,_,owner=sync;cid=record(sync);headers,_=token(sync)
    cursor=snapshot(client,headers)['changes_cursor']
    with owner.state.session_factory() as db:
        db.get(Contract,cid).designation='Rolled back';db.flush();db.rollback()
    assert changes(client,headers,cursor)['data']==[]
    with owner.state.session_factory() as db:db.get(Contract,cid).designation='Committed';db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        pages=list(pool.map(lambda _:changes(client,headers,cursor),range(2)))
    assert pages[0]['data']==pages[1]['data'] and pages[0]['data']
    with owner.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(SyncEvent))==db.scalar(select(func.count(func.distinct(SyncEvent.event_key))))


def test_document_only_upload_and_availability_advance_feed_and_v1_timestamp(sync):
    client,app,owner=sync;cid=record(sync)
    headers,_=token(sync,scopes='metadata,documents,document_content')
    cursor=snapshot(client,headers)['changes_cursor']
    with owner.state.session_factory() as db:before=db.get(Contract,cid).updated_at
    path=f'/contracts/{cid}/documents'
    form=workflow_payload(client,path,{'csrf_token':csrf_from(client.get('/').text)})
    assert client.post(path,data=form,files={'documents':('synthetic.pdf',b'%PDF-1.4\nFeed','application/pdf')},follow_redirects=False).status_code==303
    page=changes(client,headers,cursor)
    assert any(x.get('category')=='document' for x in page['data'])
    body=client.get(f'/api/v2/contracts/{cid}',headers=headers).json()['data']
    assert body['documents'][0]['state']=='available'
    assert client.get(body['documents'][0]['download_url'],headers=headers).content==b'%PDF-1.4\nFeed'
    with owner.state.session_factory() as db:assert db.get(Contract,cid).updated_at>before


@pytest.mark.parametrize('mutation',['department','revoke'])
def test_grant_change_between_authentication_and_barrier_is_revalidated(sync,monkeypatch,mutation):
    import app.integration as integration
    from threading import Event
    client,_,owner=sync
    first=record(sync);second=record(sync,'2','Other authorized scope')
    headers,identifier=token(sync,1)
    entered,released=Event(),Event();original=integration.barrier
    def paused(db):
        entered.set()
        assert released.wait(timeout=10)
        return original(db)
    monkeypatch.setattr(integration,'barrier',paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task=pool.submit(client.get,'/api/v2/snapshot',headers=headers)
        try:
            assert entered.wait(timeout=5)
            with owner.state.session_factory() as db:
                row=db.get(IntegrationToken,identifier)
                if mutation=='department':row.department_id=2
                else:row.is_active=False
                db.commit()
        finally:released.set()
        response=task.result(timeout=10)
    if mutation=='revoke':assert response.status_code==401
    else:
        assert response.status_code==200
        assert [x['id'] for x in response.json()['data']]==[second]


def test_child_events_and_archive_are_transactional(sync):
    client,_,_=sync;cid=record(sync);headers,_=token(sync,scopes='metadata,tasks,history,tax')
    cursor=snapshot(client,headers)['changes_cursor']
    csrf=csrf_from(client.get('/').text)
    for path,values in ((f'/contracts/{cid}/tasks',{'title':'Sync task','kind':'review','status':'open'}),
            (f'/contracts/{cid}/reviews',{'recipient':'K\u00e4mmerei','subject':'Sync review'})):
        assert client.post(path,data=workflow_payload(client,path,{'csrf_token':csrf,**values}),follow_redirects=False).status_code==303
    categories={x.get('category') for x in changes(client,headers,cursor)['data']}
    assert {'task','review','history'}<=categories
    from tests.test_phase4 import edit
    assert edit(client,cid,tax_review_status='not_applicable').status_code==303
    with sync[2].state.session_factory() as db:version=db.get(Contract,cid).version
    assert client.post(f'/contracts/{cid}/archive',data={'csrf_token':csrf,'version':str(version)},follow_redirects=False).status_code==303
    body=client.get(f'/api/v2/contracts/{cid}',headers=headers).json()['data']
    assert body['archived_at'] and body['tasks'] and body['reviews']


def test_usage_is_after_business_read_and_throttled(sync):
    client,app,owner=sync;record(sync);headers,identifier=token(sync,scopes='legacy_v1')
    statements=[]
    def capture(connection,cursor,statement,parameters,context,many):statements.append(statement.lower())
    event.listen(app.state.integration_engine,'before_cursor_execute',capture)
    try:
        assert client.get('/api/v1/contracts',headers=headers).status_code==200
        reads=[i for i,s in enumerate(statements) if 'from contracts' in s]
        writes=[i for i,s in enumerate(statements) if 'update integration_tokens' in s]
        assert reads and writes and max(reads)<min(writes)
        statements.clear()
        assert client.get('/api/v1/contracts',headers=headers).status_code==200
        assert not any('update integration_tokens' in s for s in statements)
    finally:event.remove(app.state.integration_engine,'before_cursor_execute',capture)
    with owner.state.session_factory() as db:assert db.get(IntegrationToken,identifier).last_used_at is not None


def test_admin_creation_rotation_overlap_and_audited_revoke(sync):
    client,_,owner=sync;record(sync)
    data={'csrf_token':csrf_from(client.get('/').text),'name':'Owned integration','expires_in':'never','api_profile':'v2','capability':['metadata'],'service_owner':'Test operations','owner_user_id':'1'}
    assert client.post('/admin/integrations',data=data).status_code==422
    data['expires_in']='90'
    response=client.post('/admin/integrations',data=data)
    assert response.status_code==200
    raw=re.search(r'<code>(ohvr_[A-Za-z0-9_-]+)</code>',response.text).group(1)
    headers={'Authorization':'Bearer '+raw}
    with owner.state.session_factory() as db:identifier=db.scalar(select(IntegrationToken.id))
    assert client.get('/api/v2/snapshot',headers=headers).status_code==200
    response=client.post(f'/admin/integrations/{identifier}/rotate',data={'csrf_token':data['csrf_token']})
    assert response.status_code==200
    replacement=re.search(r'<code>(ohvr_[A-Za-z0-9_-]+)</code>',response.text).group(1)
    assert replacement!=raw
    for auth in (headers,{'Authorization':'Bearer '+replacement}):assert client.get('/api/v2/snapshot',headers=auth).status_code==200
    assert client.post(f'/admin/integrations/{identifier}/revoke',data={'csrf_token':data['csrf_token']},follow_redirects=False).status_code==303
    assert client.get('/api/v2/snapshot',headers=headers).status_code==401


def test_admin_scope_change_requires_resnapshot_and_nonadmin_cannot_change_tokens(sync):
    from tests.test_phase4 import switch
    client,_,owner=sync;first=record(sync);second=record(sync,'2','New scope')
    headers,identifier=token(sync,1);cursor=snapshot(client,headers)['changes_cursor']
    data={'csrf_token':csrf_from(client.get('/').text),'api_scopes':'metadata,finance','service_owner':'Adopted service',
        'owner_user_id':'1','expires_in':'90','department_id':'2'}
    assert client.post(f'/admin/integrations/{identifier}/scope',data=data).status_code==200
    assert client.get('/api/v2/changes',params={'cursor':cursor},headers=headers).status_code==410
    assert [x['id'] for x in snapshot(client,headers)['data']]==[second]
    switch(client,'kultur');data['csrf_token']=csrf_from(client.get('/').text)
    for suffix in ('scope','rotate','revoke'):
        assert client.post(f'/admin/integrations/{identifier}/{suffix}',data=data).status_code==403
    with owner.state.session_factory() as db:assert db.get(IntegrationToken,identifier).department_id==2


def test_equal_timestamps_pagination_and_process_restart_do_not_omit_events(sync):
    from app.main import create_app
    from fastapi.testclient import TestClient
    client,app,owner=sync
    identifiers=[record(sync,title='Equal one'),record(sync,title='Equal two')]
    headers,_=token(sync);cursor=snapshot(client,headers)['changes_cursor']
    with owner.state.session_factory() as db:
        same=now_utc()
        for cid in identifiers:
            c=db.get(Contract,cid);c.designation+=' changed';c.updated_at=same
        db.commit()
    first=changes(client,headers,cursor,limit=1)
    assert first['has_more']
    restarted=create_app(app.state.config)
    with TestClient(restarted) as other_client:
        second=changes(other_client,headers,first['next_cursor'],limit=1)
        assert {e['contract_id'] for e in first['data']+second['data']}==set(identifiers)
        assert not second['has_more']


@pytest.mark.postgresql
def test_late_committed_outbox_id_is_not_lost_and_raw_scope_columns_are_private(sync,request):
    if request.config.getoption('--database')!='postgresql':pytest.skip('Real PostgreSQL concurrent transactions required')
    client,app,owner=sync;cid=record(sync);headers,_=token(sync)
    cursor=snapshot(client,headers)['changes_cursor'];keys=[str(uuid4()),str(uuid4())]
    with owner.state.engine.connect() as late:
        transaction=late.begin()
        late.execute(SyncOutbox.__table__.insert().values(event_key=keys[0],contract_id=cid,old_department_id=1,new_department_id=1,kind='contract'))
        with owner.state.engine.begin() as early:
            early.execute(SyncOutbox.__table__.insert().values(event_key=keys[1],contract_id=cid,old_department_id=1,new_department_id=1,kind='contract'))
        first=changes(client,headers,cursor)
        assert [x['event_id'] for x in first['data']]==[keys[1]]
        transaction.commit()
    second=changes(client,headers,first['next_cursor'])
    assert [x['event_id'] for x in second['data']]==[keys[0]]
    with app.state.integration_engine.connect() as c:
        with pytest.raises(DBAPIError):c.execute(text('SELECT old_department_id,new_department_id FROM sync_events'))


@pytest.mark.postgresql
def test_snapshot_waits_for_writer_and_includes_its_committed_state(sync,request,monkeypatch):
    if request.config.getoption('--database')!='postgresql':pytest.skip('Real PostgreSQL transaction lock required')
    from threading import Event
    import app.integration as integration
    client,_,owner=sync;cid=record(sync);headers,_=token(sync)
    entered=Event();original=integration.barrier
    def notified(db):entered.set();return original(db)
    monkeypatch.setattr(integration,'barrier',notified)
    with owner.state.session_factory() as writer,ThreadPoolExecutor(max_workers=1) as pool:
        writer.get(Contract,cid).designation='Committed before snapshot boundary';writer.flush()
        task=pool.submit(client.get,'/api/v2/snapshot',headers=headers)
        try:
            assert entered.wait(timeout=5)
            assert not task.done()
            writer.commit()
        finally:writer.rollback()
        response=task.result(timeout=10)
    assert response.status_code==200
    body=response.json()
    assert body['data'][0]['designation']=='Committed before snapshot boundary'
    assert changes(client,headers,body['changes_cursor'])['data']==[]
