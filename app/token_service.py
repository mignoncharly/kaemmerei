from app.presentation import safe_values
"""Explicit service ownership, bounded grants, overlapping rotation and deferred usage."""
from datetime import timedelta
import secrets
from threading import Lock
from time import monotonic
from fastapi import Depends,HTTPException,Request
from starlette.background import BackgroundTasks
from sqlalchemy import select,update
from app.models import IntegrationToken,User,now_utc
from app.logic import active_access
from app.identity_service import audit
from app.security import require_csrf,hash_value
from app.workflow import lock_actor
from app.integration import CAPABILITIES


def grant_fields(db,form,user):
    scopes=str(form.get('api_scopes','legacy_v1')).strip()
    if form.get('api_profile')=='v2':scopes=','.join(form.getlist('capability'))
    parts=set(scopes.split(','))
    if parts!={'legacy_v1'} and (not parts<=CAPABILITIES or 'metadata' not in parts):
        raise ValueError('Choose legacy_v1 or explicit v2 capabilities including metadata')
    if 'document_content' in parts and 'documents' not in parts:raise ValueError('document_content requires documents')
    if parts!={'legacy_v1'} and str(form.get('expires_in','90'))=='never':raise ValueError('V2 tokens require finite expiry')
    value=str(form.get('owner_user_id',user.id))
    if not value.isdecimal():raise ValueError('Active accountable owner required')
    owner=db.get(User,int(value))
    if owner is None or not active_access(owner):raise ValueError('Active accountable owner required')
    service=str(form.get('service_owner',form.get('name',''))).strip()
    if not service or len(service)>120:raise ValueError('Accountable service name required (max 120)')
    return {'api_scopes':','.join(sorted(parts)),'owner_user_id':owner.id,'service_owner':service}


def install_token_routes(app,*,get_db,user_csrf,render):
    @app.post('/admin/integrations/{token_id}/rotate')
    async def rotate(request:Request,token_id:int,db=Depends(get_db)):
        form=await request.form(max_fields=2);user,csrf=user_csrf(request,db)
        request.state.safe_values = safe_values(form)
        require_csrf(request,db,str(form.get('csrf_token','')));lock_actor(db,user)
        if user.role!='admin':raise HTTPException(403,'Administrator required')
        old=db.get(IntegrationToken,token_id)
        if old is None or not old.is_active or old.revoked_at is not None:raise HTTPException(409,'Active predecessor required')
        raw='ohvr_'+secrets.token_urlsafe(32)
        new=IntegrationToken(name=old.name,token_prefix=raw[:16],token_hash=hash_value(raw),department_id=old.department_id,
            created_by_id=user.id,owner_user_id=old.owner_user_id or user.id,service_owner=old.service_owner or old.name,
            api_scopes=old.api_scopes,rotated_from_id=old.id,expires_at=now_utc()+timedelta(days=90))
        owner=db.get(User,new.owner_user_id)
        if owner is None or not active_access(owner):raise HTTPException(409,'Adopt an active owner before rotation')
        db.add(new);db.flush();audit(db,user.id,'integration_rotated',f'token:{new.id}',predecessor_id=old.id)
        db.commit()
        return render(request,user,csrf,db,new_token=raw)

    @app.post('/admin/integrations/{token_id}/scope')
    async def rescope(request:Request,token_id:int,db=Depends(get_db)):
        form=await request.form(max_fields=8);user,csrf=user_csrf(request,db)
        request.state.safe_values = safe_values(form)
        require_csrf(request,db,str(form.get('csrf_token','')));lock_actor(db,user)
        if user.role!='admin':raise HTTPException(403,'Administrator required')
        token=db.get(IntegrationToken,token_id)
        if token is None or not token.is_active or token.revoked_at is not None:raise HTTPException(409,'Active token required')
        try:values=grant_fields(db,form,user)
        except ValueError as exc:raise HTTPException(422,str(exc)) from None
        from app.models import Department
        department=str(form.get('department_id',''))
        if department:
            if not department.isdecimal():raise HTTPException(422,'Invalid department')
            d=db.get(Department,int(department))
            if d is None or not d.is_active:raise HTTPException(422,'Inactive department')
        expiry=str(form.get('expires_in','90'))
        if expiry not in ('90','365'):raise HTTPException(422,'Finite expiry 90 or 365 required for changed grants')
        token.department_id=int(department) if department else None
        for key,value in values.items():setattr(token,key,value)
        token.expires_at=now_utc()+timedelta(days=int(expiry))
        audit(db,user.id,'integration_grant_changed',f'token:{token.id}',scopes=token.api_scopes,department_id=token.department_id,owner_user_id=token.owner_user_id)
        db.commit()
        return render(request,user,csrf,db)


def install_usage_recording(app):
    seen={};guard=Lock()
    app.state.integration_usage_failures=0
    def record(token_id,context):
        try:
            with app.state.integration_session_factory() as db:
                db.info.update(enforce_rls=app.state.config.enforce_database_security,request_context=context)
                now=now_utc()
                # Independent best-effort transaction, after the business response.
                db.execute(update(IntegrationToken).where(IntegrationToken.id==token_id,IntegrationToken.is_active.is_(True),
                    (IntegrationToken.last_used_at.is_(None))|(IntegrationToken.last_used_at<now-timedelta(minutes=5))).values(last_used_at=now))
                db.commit()
        except Exception:
            # Usage telemetry cannot change an already completed authorized read.
            # No credentials or exception text are logged.
            with guard:
                seen.pop(token_id,None)
                app.state.integration_usage_failures+=1
    @app.middleware('http')
    async def usage(request,call_next):
        response=await call_next(request)
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='private, no-store'
            if request.url.path.startswith('/api/v1/'):
                response.headers['Link']='</api/v2/snapshot>; rel="successor-version"'
        token_id=getattr(request.state,'usage_token_id',None)
        if token_id is not None and response.status_code<400:
            with guard:
                now=monotonic();due=now-seen.get(token_id,-1000)>=300
                if due:
                    if len(seen)>10000:seen.clear()
                    seen[token_id]=now
            if due:
                tasks=BackgroundTasks()
                if response.background:tasks.add_task(response.background)
                tasks.add_task(record,token_id,request.state.usage_context)
                response.background=tasks
        return response
