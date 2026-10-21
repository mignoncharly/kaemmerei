"""Version 2 state synchronization; opaque persisted cursors, never timestamp watermarks."""
from datetime import timedelta
from app.dates import contract_dates
from hashlib import sha256
import json
import secrets
from uuid import uuid4
from fastapi import Depends,HTTPException,Request
from sqlalchemy import select,text
from app.models import (Contract,ContractDocument,ContractTask,ContractReview,ReviewDecision,Revision,
    SyncState,SyncOutbox,SyncEvent,SyncCursor,SyncSnapshotItem,now_utc)
from app.authorization import contract_query,load_contract,load_child
from app.documents import download_response,audit_denied

CAPABILITIES=frozenset(('metadata','finance','documents','document_content','tax','tasks','history'))


def schema_response(name):
    return {'responses':{'200':{'description':'Capability-scoped v2 response',
        'content':{'application/json':{'schema':{'$ref':'/static/api-v2.schema.json#/$defs/'+name}}}}}}


def capabilities(token):return frozenset(token.api_scopes.split(','))


def demand(token,capability='metadata'):
    if capability not in capabilities(token):raise HTTPException(403,'Explicit v2 capability required: '+capability)
    if token.owner_user_id is None or not token.service_owner or token.expires_at is None:
        raise HTTPException(403,'Adopt an accountable owner and finite expiry for v2')


def fingerprint(token,resource=None):
    values=[2,token.id,token.department_id,token.api_scopes,token.grant_version,token.owner_user_id,token.service_owner]
    if resource is not None:values.append(resource)
    return sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest()


def barrier(db):
    if db.bind.dialect.name=='postgresql' and db.scalar(text('SHOW transaction_isolation'))!='read committed':
        raise HTTPException(503,'Synchronization requires READ COMMITTED isolation')
    if db.bind.dialect.name=='postgresql' and db.info.get('enforce_rls'):
        result=db.scalar(text('SELECT ohvr_security.sync_barrier()'))
        if result is None:raise HTTPException(401,'Token no longer authorized')
        return result
    # A write lock is held through publication and materialized snapshot creation.
    db.execute(text('UPDATE sync_state SET next_seq=next_seq WHERE id=1'))
    state=db.get(SyncState,1,populate_existing=True)
    for row in db.scalars(select(SyncOutbox).where(SyncOutbox.published_seq.is_(None)).order_by(SyncOutbox.id)):
        state.next_seq+=1
        db.add(SyncEvent(seq=state.next_seq,event_key=row.event_key,contract_id=row.contract_id,
            old_department_id=row.old_department_id,new_department_id=row.new_department_id,kind=row.kind))
        row.published_seq=state.next_seq
    db.flush()
    return {'boundary':state.next_seq,'floor':state.floor}


def make_cursor(db,token,mode,position,boundary,*,snapshot=None,expires=None,resource=None):
    raw=secrets.token_urlsafe(32)
    db.add(SyncCursor(key_hash=sha256(raw.encode()).hexdigest(),token_id=token.id,fingerprint=fingerprint(token,resource),
        mode=mode,position=position,boundary=boundary,snapshot_id=snapshot,
        expires_at=expires or now_utc()+timedelta(hours=24)))
    return raw


def get_cursor(db,token,raw,mode,floor,resource=None):
    if not raw or len(raw)>100:raise HTTPException(400,'Invalid cursor')
    cursor=db.get(SyncCursor,sha256(raw.encode()).hexdigest())
    if cursor is None or cursor.token_id!=token.id or cursor.mode!=mode:
        raise HTTPException(400,'Invalid cursor for this token/API')
    if cursor.fingerprint!=fingerprint(token,resource) or cursor.expires_at<=now_utc() or cursor.boundary<floor or (mode=='changes' and cursor.position<floor):
        raise HTTPException(410,'resnapshot_required')
    return cursor


def stamp(value):return value.isoformat()+'Z' if value else None


def bounded(db,model,cid):
    rows=db.scalars(select(model).where(model.contract_id==cid).order_by(model.id).limit(1001)).all()
    if len(rows)>1000:raise HTTPException(413,'Aggregate expansion exceeds v2 pilot bound; use a narrower capability profile')
    return rows


def payload(db,token,contract,settings):
    from app.main import safe_external_url
    caps=capabilities(token)
    result={key:getattr(contract,key) for key in ('id','contract_number','designation','contract_type','contract_partner',
        'status','department_id','version','content_revision','contact_person','deputy_contact_person')}
    result.update(relevant_date=contract.relevant_date.isoformat(),end_date=contract.end_date.isoformat() if contract.end_date else None,
        notice_period_months=contract.notice_period_months,automatic_renewal=contract.automatic_renewal,
        renewal_period_months=contract.renewal_period_months,updated_at=stamp(contract.updated_at),archived_at=stamp(contract.archived_at))
    result['calendar_estimate']={k:v.isoformat() if hasattr(v,'isoformat') else v for k,v in contract_dates(contract).items()}
    if 'finance' in caps:
        result['finance']={key:format(getattr(contract,key),'f') if getattr(contract,key) is not None else None for key in ('annual_value','contract_value')}
        result['finance'].update({key:getattr(contract,key) for key in ('financial_direction','value_basis','payment_interval','budget_assignment')})
    if 'tax' in caps:
        result['tax']={column.name:(stamp(getattr(contract,column.name)) if column.name.endswith('_at') else getattr(contract,column.name))
            for column in Contract.__table__.columns if column.name.startswith('tax_')}
    if 'documents' in caps:
        result['documents']=[{'id':d.id,'filename':d.original_filename,'state':d.state,'content_type':d.verified_media_type or d.content_type,
            'sha256':d.sha256,'size_bytes':d.size_bytes,'replaces_id':d.replaces_id,'legal_hold':d.legal_hold,
            'external_url':safe_external_url(settings,d),
            'download_url':f'/api/v2/contracts/{contract.id}/documents/{d.id}' if 'document_content' in caps and d.state=='available' else None}
            for d in bounded(db,ContractDocument,contract.id)]
    if 'tasks' in caps:
        result['tasks']=[{key:(getattr(t,key).isoformat() if key=='due_date' and getattr(t,key) else getattr(t,key)) for key in
            ('id','title','kind','status','due_date','assigned_user_id','version')} for t in bounded(db,ContractTask,contract.id)]
    if 'history' in caps:
        result['history_url']=f'/api/v2/contracts/{contract.id}/history'
        result['reviews']=[{key:getattr(r,key) for key in ('id','recipient','subject','status','result_text','content_revision','version','assigned_user_id')}
            for r in bounded(db,ContractReview,contract.id)]
        result['decisions']=[{key:(stamp(getattr(d,key)) if key=='decided_at' else getattr(d,key)) for key in
            ('id','review_id','content_revision','actor_id','status','reason','decided_at')} for d in bounded(db,ReviewDecision,contract.id)]
    return result


def install_integration_routes(app,*,get_db,authenticate):
    def prepared(request,db):
        token=authenticate(request,db);demand(token)
        state=barrier(db)
        if db.info.get('enforce_rls'):
            context=db.info['request_context']
            db.execute(text('SELECT ohvr_security.prepare_context(:session,:token,:correlation)'),
                {'session':context.get('session_hash',''),'token':context.get('token_hash',''),'correlation':context['correlation_id']})
        db.expire_all()
        token=authenticate(request,db);demand(token)
        return token,state

    @app.get('/api/v2/snapshot',openapi_extra=schema_response('SnapshotPage'))
    def snapshot(request:Request,cursor:str='',limit:int=100,db=Depends(get_db)):
        if not 1<=limit<=500:raise HTTPException(400,'limit must be 1..500')
        token,state=prepared(request,db)
        if not cursor:
            contracts=db.scalars(contract_query(token).order_by(Contract.id).limit(5001)).all()
            if len(contracts)>5000:raise HTTPException(413,'Snapshot exceeds 5000-contract pilot bound; use department-scoped tokens')
            snapshot_id=str(uuid4());boundary=state['boundary'];position=0;expires=now_utc()+timedelta(hours=24)
            for index,contract in enumerate(contracts,1):
                db.add(SyncSnapshotItem(snapshot_id=snapshot_id,position=index,token_id=token.id,contract_id=contract.id,payload=payload(db,token,contract,app.state.config)))
            db.flush()
        else:
            old=get_cursor(db,token,cursor,'snapshot',state['floor'])
            snapshot_id,boundary,position,expires=old.snapshot_id,old.boundary,old.position,old.expires_at
        rows=db.scalars(select(SyncSnapshotItem).where(SyncSnapshotItem.snapshot_id==snapshot_id,
            SyncSnapshotItem.token_id==token.id,SyncSnapshotItem.position>position).order_by(SyncSnapshotItem.position).limit(limit+1)).all()
        more=len(rows)>limit;page=rows[:limit];data=[]
        for row in page:
            if db.scalar(contract_query(token).where(Contract.id==row.contract_id)) is not None:data.append(row.payload)
        position=page[-1].position if page else position
        next_cursor=make_cursor(db,token,'snapshot',position,boundary,snapshot=snapshot_id,expires=expires) if more else None
        changes_cursor=None if more else make_cursor(db,token,'changes',boundary,boundary,expires=expires)
        db.commit()
        return {'api_version':2,'data':data,'next_cursor':next_cursor,'changes_cursor':changes_cursor,'snapshot_expires_at':stamp(expires)}

    @app.get('/api/v2/changes',openapi_extra=schema_response('ChangesPage'))
    def changes(request:Request,cursor:str,limit:int=100,db=Depends(get_db)):
        if not 1<=limit<=500:raise HTTPException(400,'limit must be 1..500')
        token,state=prepared(request,db);old=get_cursor(db,token,cursor,'changes',state['floor'])
        restricted=db.bind.dialect.name=='postgresql' and db.info.get('enforce_rls')
        if restricted:
            rows=db.execute(text('SELECT * FROM ohvr_security.sync_events_page(:position,:size)'),{'position':old.position,'size':limit+1}).all()
        else:
            query=select(SyncEvent).where(SyncEvent.seq>old.position)
            if token.department_id is not None:query=query.where((SyncEvent.old_department_id==token.department_id)|(SyncEvent.new_department_id==token.department_id))
            rows=db.scalars(query.order_by(SyncEvent.seq).limit(limit+1)).all()
        more=len(rows)>limit;page=rows[:limit];data=[]
        for row in page:
            visible=db.scalar(contract_query(token).where(Contract.id==row.contract_id)) is not None
            removal=row.removed if restricted else not visible or (token.department_id is not None and row.new_department_id!=token.department_id)
            item={'event_id':row.event_key,'contract_id':row.contract_id,'operation':'remove' if removal else 'upsert'}
            if removal:item['reason']='no_longer_authorized'
            else:item['resource_url']=f'/api/v2/contracts/{row.contract_id}';item['category']=row.kind
            data.append(item)
        position=page[-1].seq if more else state['boundary']
        next_cursor=make_cursor(db,token,'changes',position,position)
        db.commit()
        return {'api_version':2,'data':data,'next_cursor':next_cursor,'has_more':more}

    @app.get('/api/v2/contracts/{contract_id}',openapi_extra=schema_response('ContractResponse'))
    def detail(request:Request,contract_id:int,db=Depends(get_db)):
        token=authenticate(request,db);demand(token)
        return {'api_version':2,'data':payload(db,token,load_contract(db,token,contract_id),app.state.config)}

    @app.get('/api/v2/contracts/{contract_id}/history',openapi_extra=schema_response('HistoryPage'))
    def history(request:Request,contract_id:int,cursor:str='',limit:int=100,db=Depends(get_db)):
        if not 1<=limit<=500 or 'after_id' in request.query_params:raise HTTPException(400,'Use opaque history cursors and limit 1..500')
        token,state=prepared(request,db);demand(token,'history');load_contract(db,token,contract_id)
        if not cursor:
            source=db.scalars(select(Revision).where(Revision.contract_id==contract_id).order_by(Revision.id).limit(5001)).all()
            if len(source)>5000:raise HTTPException(413,'History exceeds 5000-row pilot snapshot bound')
            sid=str(uuid4());position=0;boundary=state['boundary'];expires=now_utc()+timedelta(hours=24)
            for index,row in enumerate(source,1):
                db.add(SyncSnapshotItem(snapshot_id=sid,position=index,token_id=token.id,contract_id=contract_id,
                    payload={'id':row.id,'action':row.action,'actor_id':row.actor_id,'created_at':stamp(row.created_at),'before':row.before,'after':row.after}))
            db.flush()
        else:
            old=get_cursor(db,token,cursor,'history',state['floor'],resource=contract_id)
            sid,position,boundary,expires=old.snapshot_id,old.position,old.boundary,old.expires_at
        rows=db.scalars(select(SyncSnapshotItem).where(SyncSnapshotItem.snapshot_id==sid,SyncSnapshotItem.token_id==token.id,
            SyncSnapshotItem.contract_id==contract_id,SyncSnapshotItem.position>position).order_by(SyncSnapshotItem.position).limit(limit+1)).all()
        page=rows[:limit]
        next_cursor=make_cursor(db,token,'history',page[-1].position,boundary,snapshot=sid,expires=expires,resource=contract_id) if len(rows)>limit else None
        result={'api_version':2,'data':[r.payload for r in page],'next_cursor':next_cursor,'snapshot_expires_at':stamp(expires)}
        db.commit()
        return result

    @app.get('/api/v2/contracts/{contract_id}/documents/{document_id}')
    def document(request:Request,contract_id:int,document_id:int,db=Depends(get_db)):
        token=authenticate(request,db);demand(token,'document_content')
        try:_,row=load_child(db,token,contract_id,ContractDocument,document_id)
        except HTTPException:
            audit_denied(db,document_id,token=token);raise
        return download_response(db,app.state.config,row,request,token=token)
