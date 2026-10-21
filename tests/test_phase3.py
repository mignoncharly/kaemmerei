"""Schema and restricted-role RLS acceptance, never replaced by SQLite evidence."""
import pytest
from contextlib import contextmanager
from uuid import uuid4
from sqlalchemy import text,select,create_engine
from sqlalchemy.exc import DBAPIError
from app.db import make_session_factory,make_engine
from app.db_roles import validate_runtime_engine
from app.config import Settings
from app.models import Contract,ContractReview,IntegrationToken,LoginSession,now_utc
from app.security import COOKIE_NAME,hash_value
from tests.support import login,create_contract,csrf_from
from tests.runtime_support import runtime_environment


@contextmanager
def runtime_session(runtime,*,cookie='',token='',integration=False,factory=None):
    factory=factory or (runtime.app.state.integration_session_factory if integration else runtime.app.state.session_factory)
    with factory() as db:
        db.info['enforce_rls']=True
        db.info['request_context']={'session_hash':hash_value(cookie) if cookie else '',
            'token_hash':hash_value(token) if token else '', 'correlation_id':str(uuid4())}
        yield db


def switch(client,user):
    client.post('/logout',data={'csrf_token':csrf_from(client.get('/').text)})
    assert login(client,user).status_code==303


def seeded_contracts(runtime):
    client=runtime.client
    assert login(client,'admin').status_code==303
    first,second=create_contract(client,'1','Synthetic A'),create_contract(client,'2','Synthetic B')
    csrf=csrf_from(client.get('/').text)
    for record in (first,second):
        assert client.post(f'/contracts/{record}/reviews',data={'csrf_token':csrf,'recipient':'Kämmerei','subject':'Synthetic review'},follow_redirects=False).status_code==303
        assert client.post(f'/contracts/{record}/tasks',data={'csrf_token':csrf,'kind':'review','title':'Synthetic task'},follow_redirects=False).status_code==303
        assert client.post(f'/contracts/{record}/documents',data={'csrf_token':csrf},files={'documents':('synthetic.pdf',b'%PDF-1.4\nSynthetic','application/pdf')},follow_redirects=False).status_code==303
    return first,second


@pytest.fixture
def runtime(request):
    if request.config.getoption('--database')!='postgresql':
        pytest.skip('Actual restricted PostgreSQL login roles required')
    with runtime_environment() as value:
        yield value


@pytest.mark.postgresql
def test_restricted_runtime_application_smoke(runtime):
    from tests.support import contract_payload
    client=runtime.client
    assert login(client,'admin').status_code==303
    record=create_contract(client)
    assert client.get(f'/contracts/{record}').status_code==200
    form=client.get(f'/contracts/{record}/edit')
    values=contract_payload(designation='Restricted updated contract')
    values.update(csrf_token=csrf_from(form.text),version='1')
    assert client.post(f'/contracts/{record}/edit',data=values,follow_redirects=False).status_code==303
    assert client.post(f'/contracts/{record}/edit',data=values).status_code==409
    csrf=csrf_from(client.get('/').text)
    assert client.post(f'/contracts/{record}/reviews',data={'csrf_token':csrf,'recipient':'Kämmerei','subject':'Archive barrier'},follow_redirects=False).status_code==303
    with runtime.owner.state.session_factory() as db:
        review_id=db.scalar(select(ContractReview.id).where(ContractReview.contract_id==record))
    assert client.post(f'/contracts/{record}/archive',data={'csrf_token':csrf,'version':'2'},follow_redirects=False).status_code==303
    assert client.get(f'/contracts/{record}/edit').status_code==409
    assert client.post(f'/contracts/{record}/reviews/{review_id}',data={'csrf_token':csrf,'status':'approved','result_text':'Denied'}).status_code==409
    with runtime_session(runtime,cookie=client.cookies.get(COOKIE_NAME)) as db:
        assert db.execute(text("UPDATE contract_reviews SET status='approved' WHERE id=:id"),{'id':review_id}).rowcount==0
        assert db.scalars(text('SELECT action FROM revisions WHERE contract_id=:id ORDER BY id'),{'id':record}).all()==['created','updated','review_created','archived']
    with runtime.app.state.engine.connect() as connection:
        assert connection.scalar(text('SELECT current_user'))==runtime.names['web']


@pytest.mark.postgresql
def test_unscoped_queries_children_joins_and_department_moves_are_enforced(runtime):
    first,second=seeded_contracts(runtime)
    switch(runtime.client,'kultur')
    cookie=runtime.client.cookies.get(COOKIE_NAME)
    with runtime_session(runtime,cookie=cookie) as db:
        assert db.scalars(text('SELECT id FROM contracts')).all()==[first]
        for table in ('contract_documents','contract_tasks','contract_reviews','revisions','security_events'):
            assert set(db.scalars(text(f'SELECT contract_id FROM {table}'))) == {first}
        assert db.execute(text('UPDATE contracts SET designation=designation WHERE id=:id'),{'id':second}).rowcount==0
        assert db.scalars(text('SELECT c.id FROM contracts c JOIN contract_documents d ON d.contract_id=c.id')).all()==[first]
        with pytest.raises(DBAPIError),db.begin_nested():
            db.execute(text('UPDATE contracts SET department_id=2 WHERE id=:id'),{'id':first})
        with pytest.raises(DBAPIError),db.begin_nested():
            db.execute(text("INSERT INTO contract_tasks(contract_id,title,kind,status,description,created_by_id,created_at,updated_at) VALUES(:id,'Forbidden','review','open','',2,:stamp,:stamp)"),{'id':second,'stamp':now_utc()})
        with pytest.raises(DBAPIError),db.begin_nested():
            db.execute(text('UPDATE contract_documents SET contract_id=:id'),{'id':second})


@pytest.mark.postgresql
def test_guest_invalid_malformed_context_and_readonly_reviewer_default_to_denial(runtime):
    first,second=seeded_contracts(runtime)
    for cookie in ('','not-a-valid-session'):
        with runtime_session(runtime,cookie=cookie) as db:
            assert db.scalar(text('SELECT count(*) FROM contracts'))==0
    with runtime_session(runtime) as db:
        for malformed in ('not-json','{}','{"kind":"user","id":"bad","role":"admin"}',
                          '{"kind":"user","id":"9999999999999999999999999","role":"admin","forced":false}'):
            db.execute(text("SELECT set_config('ohvr.principal',:value,true)"),{'value':malformed})
            assert db.scalar(text('SELECT count(*) FROM contracts'))==0
    switch(runtime.client,'pruefer')
    with runtime_session(runtime,cookie=runtime.client.cookies.get(COOKIE_NAME)) as db:
        assert set(db.scalars(text('SELECT id FROM contracts')))=={first,second}
        assert db.execute(text("UPDATE contracts SET designation='denied'")).rowcount==0
        assert db.execute(text("UPDATE contract_reviews SET status='approved' ")).rowcount==0


@pytest.mark.postgresql
def test_integration_role_scoped_api_post_commit_and_credential_denials(runtime):
    first,second=seeded_contracts(runtime)
    raw='ohvr_'+'P'*32
    with runtime.owner.state.session_factory() as db:
        db.add(IntegrationToken(name='Scoped',token_prefix=raw[:16],token_hash=hash_value(raw),department_id=1,created_by_id=1))
        db.commit()
    headers={'Authorization':'Bearer '+raw}
    response=runtime.client.get('/api/v1/contracts',headers=headers)
    assert response.status_code==200
    assert [c['id'] for c in response.json()['data']]==[first]
    doc=response.json()['data'][0]['documents'][0]['id']
    assert runtime.client.get(f'/api/v1/contracts/{first}/documents/{doc}',headers=headers).status_code==200
    assert runtime.client.get(f'/api/v1/contracts/{second}/documents/{doc}',headers=headers).status_code==404
    with runtime_session(runtime,token=raw,integration=True) as db:
        assert db.scalars(text('SELECT id FROM contracts')).all()==[first]
        assert set(db.scalars(text('SELECT contract_id FROM security_events')))=={first}
        for query in ('SELECT password_hash FROM users','SELECT token_hash FROM integration_tokens',
                      'SELECT * FROM login_sessions','SELECT ohvr_security.password_hash(1)',
                      "UPDATE contracts SET designation='denied'",'SELECT ohvr_security.purge_expired()'):
            with pytest.raises(DBAPIError),db.begin_nested():
                db.execute(text(query))


@pytest.mark.postgresql
def test_pool_reuse_commit_and_rollback_never_retain_identity(runtime):
    first,second=seeded_contracts(runtime)
    switch(runtime.client,'kultur')
    first_cookie=runtime.client.cookies.get(COOKIE_NAME)
    switch(runtime.client,'bau')
    second_cookie=runtime.client.cookies.get(COOKIE_NAME)
    engine=create_engine(runtime.urls['web'],pool_size=1,max_overflow=0,hide_parameters=True)
    factory=make_session_factory(engine)
    try:
        pids=[]
        for cookie,expected in ((first_cookie,first),(second_cookie,second),(first_cookie,first)):
            # The first cookie was explicitly logged out by switch(). Restore an
            # independent synthetic session under the owner for this pool test.
            with runtime.owner.state.session_factory() as owner:
                if owner.get(LoginSession,hash_value(cookie)) is None:
                    from datetime import timedelta
                    owner.add(LoginSession(token_hash=hash_value(cookie),user_id=2 if expected==first else 3,
                        csrf_token='synthetic',expires_at=now_utc()+timedelta(hours=1)))
                    owner.commit()
            with runtime_session(runtime,cookie=cookie,factory=factory) as db:
                pids.append(db.scalar(text('SELECT pg_backend_pid()')))
                assert db.scalars(text('SELECT id FROM contracts')).all()==[expected]
                db.commit()
                assert db.scalars(text('SELECT id FROM contracts')).all()==[expected]
                db.rollback()
            with engine.connect() as connection:
                assert connection.scalar(text('SELECT count(*) FROM contracts'))==0
                assert connection.scalar(text("SELECT current_setting('ohvr.principal',true)")) in ('',None)
        assert len(set(pids))==1
    finally:
        engine.dispose()


@pytest.mark.postgresql
def test_audit_rows_cannot_be_updated_deleted_truncated_or_directly_forged(runtime):
    seeded_contracts(runtime)
    cookie=runtime.client.cookies.get(COOKIE_NAME)
    with runtime_session(runtime,cookie=cookie) as db:
        row=db.execute(text('SELECT actor_id,principal,outcome,correlation_id FROM security_events ORDER BY id DESC LIMIT 1')).one()
        assert row.actor_id==1 and row.principal=='user' and row.outcome=='success' and len(row.correlation_id)==36
        for table in ('revisions','identity_audit','security_events'):
            for statement in (f'UPDATE {table} SET action=action',f'DELETE FROM {table}',f'TRUNCATE {table}'):
                with pytest.raises(DBAPIError),db.begin_nested():
                    db.execute(text(statement))
        with pytest.raises(DBAPIError),db.begin_nested():
            db.execute(text("INSERT INTO security_events(principal,action,target,outcome,correlation_id,created_at,details) VALUES('admin','fake','fake','success','fake',:stamp,'{}')"),{'stamp':now_utc()})
        with pytest.raises(DBAPIError),db.begin_nested():
            db.execute(text('SELECT password_hash FROM users'))


@pytest.mark.postgresql
def test_password_rotation_admin_identity_changes_and_review_permissions_under_runtime_role(runtime):
    from tests.support import PASSWORD,contract_payload
    record,_=seeded_contracts(runtime)
    switch(runtime.client,'kultur')
    csrf=csrf_from(runtime.client.get('/account/password').text)
    result=runtime.client.post('/account/password',data={'csrf_token':csrf,'current_password':PASSWORD,
        'new_password':'Restricted-Role-Changed-Password-2026','confirm_password':'Restricted-Role-Changed-Password-2026'},follow_redirects=False)
    assert result.status_code==303
    assert runtime.client.get('/').status_code==200
    switch(runtime.client,'admin')
    assert runtime.client.get('/admin/identities').status_code==200
    assert runtime.client.post('/admin/identities/departments/1',data={'csrf_token':csrf_from(runtime.client.get('/').text),
        'name':'Scoped renamed','is_active':'1'},follow_redirects=False).status_code==303
    with runtime.owner.state.session_factory() as db:
        review=db.scalar(select(ContractReview).where(ContractReview.contract_id==record))
        review_id=review.id
    assert runtime.client.post(f'/contracts/{record}/reviews/{review_id}',data={'csrf_token':csrf_from(runtime.client.get('/').text),
        'status':'approved','result_text':'Runtime decision'},follow_redirects=False).status_code==303
    with runtime.owner.state.session_factory() as db:
        assert db.get(ContractReview,review_id).status=='approved'


@pytest.mark.postgresql
def test_maintenance_is_narrow_and_production_rejects_owner_connection(runtime):
    from datetime import timedelta
    with runtime.owner.state.session_factory() as db:
        db.add(LoginSession(token_hash='e'*64,csrf_token='synthetic',expires_at=now_utc()-timedelta(days=1)))
        db.add(LoginSession(token_hash='f'*64,csrf_token='synthetic',expires_at=now_utc()+timedelta(days=1)))
        db.commit()
    engine=make_engine(Settings(database_url=runtime.urls['maintenance']))
    try:
        with engine.begin() as connection:
            connection.execute(text('SELECT ohvr_security.purge_expired()'))
            for query in ('SELECT * FROM users','SELECT * FROM contracts','SELECT * FROM login_sessions'):
                with pytest.raises(DBAPIError),connection.begin_nested():
                    connection.execute(text(query))
    finally:
        engine.dispose()
    with runtime.owner.state.session_factory() as db:
        assert db.get(LoginSession,'e'*64) is None
        assert db.get(LoginSession,'f'*64) is not None
    with pytest.raises(ValueError,match='restricted'):
        validate_runtime_engine(runtime.owner.state.engine,'web')


@pytest.mark.postgresql
def test_assigned_approval_revocation_and_self_escalation_under_runtime_role(runtime):
    from app.models import User,RecipientTeam,RecipientMembership
    record,_=seeded_contracts(runtime)
    with runtime.owner.state.session_factory() as db:
        user=db.scalar(select(User).where(User.username=='pruefer'))
        user.can_approve=True
        team=RecipientTeam(name='Synthetic approval team')
        db.add(team)
        db.flush()
        db.add(RecipientMembership(team_id=team.id,user_id=user.id))
        review=db.scalar(select(ContractReview).where(ContractReview.contract_id==record))
        review.team_id,review.assigned_user_id=team.id,user.id
        team_id,user_id,review_id=team.id,user.id,review.id
        db.commit()
    switch(runtime.client,'pruefer')
    path=f'/contracts/{record}/reviews/{review_id}'
    data={'csrf_token':csrf_from(runtime.client.get('/').text),'status':'approved','result_text':'Authorized'}
    assert runtime.client.post(path,data=data,follow_redirects=False).status_code==303
    with runtime_session(runtime,cookie=runtime.client.cookies.get(COOKIE_NAME)) as db:
        with pytest.raises(DBAPIError),db.begin_nested():
            db.execute(text("UPDATE users SET role='admin' WHERE id=:id"),{'id':user_id})
        with pytest.raises(DBAPIError),db.begin_nested():
            db.execute(text('UPDATE contract_reviews SET assigned_user_id=1 WHERE id=:id'),{'id':review_id})
    with runtime.owner.state.session_factory() as db:
        db.delete(db.get(RecipientMembership,(team_id,user_id)))
        db.commit()
    assert runtime.client.post(path,data=data).status_code==403
    with runtime_session(runtime,cookie=runtime.client.cookies.get(COOKIE_NAME)) as db:
        assert db.execute(text("UPDATE contract_reviews SET status='rejected' WHERE id=:id"),{'id':review_id}).rowcount==0


@pytest.mark.postgresql
def test_context_revalidates_revocation_and_auth_functions_are_hardened(runtime):
    first,_=seeded_contracts(runtime)
    switch(runtime.client,'kultur')
    cookie=runtime.client.cookies.get(COOKIE_NAME)
    with runtime_session(runtime,cookie=cookie) as db:
        assert db.scalar(text('SELECT count(*) FROM contracts'))==1
        db.commit()
        with runtime.owner.state.session_factory() as owner:
            owner.delete(owner.get(LoginSession,hash_value(cookie)))
            owner.commit()
        assert db.scalar(text('SELECT count(*) FROM contracts'))==0
    with runtime.owner.state.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='ohvr_security' AND p.prosecdef AND NOT ('search_path=pg_catalog, pg_temp'=ANY(p.proconfig) OR 'search_path=pg_catalog,pg_temp'=ANY(p.proconfig))"))==0
        assert connection.scalar(text("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE n.nspname='ohvr_security' AND a.grantee=0 AND a.privilege_type='EXECUTE'"))==0
        assert connection.scalar(text("SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner WHERE c.relname IN ('revisions','identity_audit','security_events') AND r.rolname=:owner AND NOT r.rolcanlogin"),{'owner':runtime.names['audit']})==3


@pytest.mark.postgresql
def test_operator_cli_uses_explicit_owner_and_maintenance_connections(runtime,monkeypatch,capsys):
    from dataclasses import replace
    from app import cli
    base=runtime.app.state.config
    monkeypatch.setattr(cli,'get_settings',lambda:base)
    monkeypatch.setattr('sys.argv',['ohvr','purge-sessions'])
    with pytest.raises(SystemExit,match='Explicit'):
        cli.main()
    configured=replace(base,migration_database_url=runtime.owner.state.config.database_url,
                       maintenance_database_url=runtime.urls['maintenance'])
    monkeypatch.setattr(cli,'get_settings',lambda:configured)
    cli.main()
    assert 'maintenance privileges' in capsys.readouterr().out
    monkeypatch.setattr('sys.argv',['ohvr','schema-inventory'])
    cli.main()
    assert '"schema": [], "legacy": []' in capsys.readouterr().out
