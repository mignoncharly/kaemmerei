"""Human TOTP challenges, actual role boundary, recovery; synthetic identities."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
import re
from urllib.parse import quote
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pyotp
import pytest
from sqlalchemy import delete,select,text
from sqlalchemy.exc import DBAPIError

from app.main import create_app
from app.config import Settings
from app.db import make_engine,make_session_factory
from app.mfa_codec import SeedCipher
from app.mfa_service import authorize_enrollment,enforce_policy,required_for
from app.models import IntegrationToken,LoginSession,MfaCredential,MfaPolicy,SecurityEvent,User,now_utc
from app.security import COOKIE_NAME,hash_value
from tests.runtime_support import runtime_environment
from tests.scanner_support import CleanScanner
from tests.support import environment_context,login,csrf_from,create_contract,PASSWORD
from tests.test_phase3 import runtime_session
from tests.backup_support import restored_fixture


@pytest.fixture
def mfa(request):
    def configured(base,owner):
        path=Path(owner.state.document_storage_dir).parent/'mfa-test-keys.json'
        path.write_text(json.dumps([Fernet.generate_key().decode()]),encoding='utf-8')
        with owner.state.session_factory() as db:
            for name in ('admin','kultur','bau','pruefer'):
                authorize_enrollment(db,name,'SYNTHETIC-CASE')
            enforce_policy(db,'SYNTHETIC-ROLLOUT')
            db.commit()
        app=create_app(replace(base.state.config,require_mfa=True,mfa_key_file=path))
        app.state.document_scanner=CleanScanner()
        return app
    if request.config.getoption('--database')=='postgresql':
        with runtime_environment() as runtime:
            app=configured(runtime.app,runtime.owner)
            with TestClient(app) as client:yield client,app,runtime.owner,runtime
    else:
        with environment_context('sqlite') as (_,owner):
            app=configured(owner,owner)
            with TestClient(app) as client:yield client,app,owner,None


def start(client,name='admin'):
    response=login(client,name)
    assert response.status_code==303 and response.headers['location']=='/account/mfa'
    page=client.get('/account/mfa')
    assert page.status_code==200
    response=client.post('/account/mfa/start',data={'csrf_token':csrf_from(page.text)},follow_redirects=False)
    assert response.status_code==303
    page=client.get('/account/mfa')
    match=re.search(r'id="enrollment-secret" value="([A-Z2-7]{32})"',page.text)
    assert match
    return match.group(1),csrf_from(page.text)


def enroll(client,name='admin'):
    seed,csrf=start(client,name)
    code=pyotp.TOTP(seed).now()
    response=client.post('/account/mfa',data={'csrf_token':csrf,'code':code},follow_redirects=False)
    assert response.status_code==303 and response.headers['location']=='/'
    assert client.get('/').status_code==200
    return seed,code


def test_enrollment_is_csrf_protected_private_and_not_an_authenticated_session(mfa):
    client,app,owner,_=mfa
    assert login(client,'admin').headers['location']=='/account/mfa'
    assert client.get('/contracts/new',follow_redirects=False).status_code==303
    assert client.post('/account/mfa/start',data={'csrf_token':'wrong'}).status_code==403
    page=client.get('/account/mfa')
    assert 'enrollment-secret' not in page.text
    assert 'no-store' in {part.strip() for part in page.headers['cache-control'].split(',')}
    client.post('/account/mfa/start',data={'csrf_token':csrf_from(page.text)})
    page=client.get('/account/mfa');seed=re.search(r'id="enrollment-secret" value="([A-Z2-7]{32})"',page.text).group(1)
    with owner.state.session_factory() as db:
        credential=db.get(MfaCredential,db.scalar(select(User.id).where(User.username=='admin')))
        assert not credential.enabled and seed not in credential.seed_ciphertext
        assert app.state.mfa_cipher.decrypt(credential.user_id,credential.seed_ciphertext)==seed
    response=client.post('/account/mfa',data={'csrf_token':csrf_from(page.text),'code':pyotp.TOTP(seed).now()},follow_redirects=False)
    assert response.status_code==303 and client.get('/contracts/new').status_code==200
    with owner.state.session_factory() as db:
        record=db.get(LoginSession,hash_value(client.cookies.get(COOKIE_NAME)))
        assert record.mfa_verified and record.pending_user_id is None
        assert db.scalar(select(SecurityEvent.id).where(SecurityEvent.action=='MFA_ENROLLED'))


def test_replay_across_fresh_password_challenges_is_denied(mfa):
    client,_,owner,_=mfa
    seed,code=enroll(client)
    assert login(client,'admin').headers['location']=='/account/mfa'
    page=client.get('/account/mfa')
    assert seed not in page.text and 'enrollment-secret' not in page.text
    denied=client.post('/account/mfa',data={'csrf_token':csrf_from(page.text),'code':code})
    assert denied.status_code==401 and seed not in denied.text and code not in denied.text
    assert client.get('/',follow_redirects=False).status_code==303
    with owner.state.session_factory() as db:
        assert db.scalar(select(SecurityEvent.id).where(SecurityEvent.action=='MFA_DENIED'))


def test_wrong_codes_burn_challenge_and_expiry_does_not_extend(mfa):
    client,_,owner,_=mfa
    _,csrf=start(client)
    raw=client.cookies.get(COOKIE_NAME)
    for i in range(5):
        response=client.post('/account/mfa',data={'csrf_token':csrf,'code':'invalid'},follow_redirects=False)
        assert response.status_code==(303 if i==4 else 401)
    with owner.state.session_factory() as db:assert db.get(LoginSession,hash_value(raw)) is None
    assert login(client,'admin').headers['location']=='/account/mfa'
    raw=client.cookies.get(COOKIE_NAME)
    with owner.state.session_factory() as db:
        db.get(LoginSession,hash_value(raw)).expires_at=now_utc()-timedelta(seconds=1)
        db.commit()
    assert client.get('/account/mfa',follow_redirects=False).status_code==303


def test_enrollment_requires_operator_authorization_and_never_restores_inactive_access(mfa):
    client,_,owner,_=mfa
    with owner.state.session_factory() as db:
        user=db.scalar(select(User).where(User.username=='kultur'))
        credential=db.get(MfaCredential,user.id)
        credential.authorization_expires_at=now_utc()-timedelta(seconds=1)
        db.commit()
    assert login(client,'kultur').headers['location']=='/account/mfa'
    assert client.get('/account/mfa').status_code==403
    with owner.state.session_factory() as db:
        user=db.scalar(select(User).where(User.username=='kultur'));user.department.is_active=False;db.commit()
        with pytest.raises(ValueError):authorize_enrollment(db,'kultur','CASE',recovery=True)
        db.rollback()
    assert client.post('/account/mfa',data={'csrf_token':'unused','code':'000000'}).status_code==403


def test_recovery_revokes_full_and_pending_sessions_and_requires_new_enrollment(mfa):
    client,app,owner,_=mfa
    old_seed,_=enroll(client)
    full_cookie=client.cookies.get(COOKIE_NAME)
    assert login(client,'admin').headers['location']=='/account/mfa'
    pending_cookie=client.cookies.get(COOKIE_NAME)
    with owner.state.session_factory() as db:
        authorize_enrollment(db,'admin','SYNTHETIC-RECOVERY',recovery=True);db.commit()
        assert db.get(LoginSession,hash_value(full_cookie)) is None
        assert db.get(LoginSession,hash_value(pending_cookie)) is None
        assert db.scalar(select(User).where(User.username=='admin')).must_change_password
    seed,csrf=start(client)
    assert seed!=old_seed
    response=client.post('/account/mfa',data={'csrf_token':csrf,'code':pyotp.TOTP(seed).now()},follow_redirects=False)
    assert response.status_code==303
    assert client.get('/',follow_redirects=False).headers['location']=='/account/password'


def test_password_change_preserves_verified_factor_and_revokes_pending_challenges(mfa):
    client,app,owner,_=mfa
    enroll(client,'kultur')
    with TestClient(app) as other:
        assert login(other,'kultur').headers['location']=='/account/mfa'
        pending=other.cookies.get(COOKIE_NAME)
        page=client.get('/account/password')
        assert page.status_code==200
        response=client.post('/account/password',data={'csrf_token':csrf_from(page.text),
            'current_password':PASSWORD,'new_password':'Synthetic-Replacement-Password-2026',
            'confirm_password':'Synthetic-Replacement-Password-2026'},follow_redirects=False)
        assert response.status_code==303 and client.get('/').status_code==200
        with owner.state.session_factory() as db:
            assert db.get(LoginSession,hash_value(pending)) is None
            assert db.get(LoginSession,hash_value(client.cookies.get(COOKIE_NAME))).mfa_verified


def test_bounded_operator_key_rotation_keeps_factor_state_and_emits_no_secrets(mfa,capsys):
    client,app,owner,_=mfa
    seed,_=enroll(client)
    path=app.state.config.mfa_key_file
    old_keys=json.loads(path.read_text())
    primary=Fernet.generate_key().decode()
    path.write_text(json.dumps([primary,*old_keys]),encoding='utf-8')
    app.state.mfa_cipher=SeedCipher(path)  # mirrors required restart before rotation
    from app.cli import main
    settings=replace(owner.state.config,mfa_key_file=path)
    with patch('app.cli.get_settings',return_value=settings),patch('sys.argv',['ohvr','mfa-key-rotate','--limit','1']):
        main()
    output=capsys.readouterr().out
    assert json.loads(output)['rotated']==1 and seed not in output and primary not in output
    with owner.state.session_factory() as db:
        credential=db.get(MfaCredential,db.scalar(select(User.id).where(User.username=='admin')))
        assert credential.enabled and credential.last_step>=0
        path.write_text(json.dumps([primary]),encoding='utf-8')
        assert SeedCipher(path).decrypt(credential.user_id,credential.seed_ciphertext)==seed


@pytest.mark.parametrize('args',[
    ['mfa-enroll-authorize','synthetic','--reference','CASE'],
    ['mfa-recover','synthetic','--reference','CASE'],
    ['mfa-enforce','--reference','CASE']])
def test_operator_commands_require_explicit_verification_or_revocation_flag(args,capsys):
    from app.cli import main
    with patch('sys.argv',['ohvr',*args]),pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code==2
    capsys.readouterr()


def test_key_configuration_rejects_relative_served_and_document_locations():
    for path in (Path('relative.json'),Path.cwd()/'app'/'static'/'..'/'static'/'key.json',
                 Settings.document_storage_dir/'keys.json'):
        with pytest.raises(ValueError):replace(Settings(),mfa_key_file=path).validate()


def test_human_mfa_startup_requires_explicit_database_policy():
    with environment_context('sqlite') as (_,owner):
        key=Path(owner.state.document_storage_dir).parent/'startup-test-key.json'
        key.write_text(json.dumps([Fernet.generate_key().decode()]),encoding='utf-8')
        app=create_app(replace(owner.state.config,require_mfa=True,mfa_key_file=key))
        with pytest.raises(ValueError,match='enable database MFA policy'),TestClient(app):
            pass


def test_production_cannot_select_password_only_or_release_directory_keys():
    ca=quote(str(Path.cwd()/'synthetic-ca.pem'),safe='')
    query='?sslmode=verify-full&sslrootcert='+ca
    settings=Settings(environment='production',allowed_hosts=('contracts.example.invalid',),
        database_url='postgresql+psycopg://web@db.invalid/register'+query,
        integration_database_url='postgresql+psycopg://integration@db.invalid/register'+query,
        enforce_database_security=True)
    with pytest.raises(ValueError,match='MFA_KEY_FILE'):settings.validate()
    with pytest.raises(ValueError,match='release/project'):
        replace(settings,mfa_key_file=Path.cwd()/'keys.json').validate()


def test_missing_policy_fails_closed_instead_of_selecting_password_only(mfa):
    _,app,owner,runtime=mfa
    with owner.state.session_factory() as db:
        db.execute(delete(MfaPolicy));db.commit()
    if runtime is not None:
        with app.state.engine.connect() as connection,pytest.raises(DBAPIError):
            connection.scalar(text('SELECT ohvr_security.mfa_policy_required()'))
    else:
        with owner.state.session_factory() as db,pytest.raises(ValueError,match='MFA policy is missing'):
            required_for(db,1)


def test_encrypted_seed_and_mfa_audit_survive_real_database_restore(mfa,request):
    client,app,owner,_=mfa
    seed,_=enroll(client)
    with owner.state.session_factory() as db:
        user_id=db.scalar(select(User.id).where(User.username=='admin'))
        original=db.get(MfaCredential,user_id)
        ciphertext,step=original.seed_ciphertext,original.last_step
        audit_id=db.scalar(select(SecurityEvent.id).where(SecurityEvent.action=='MFA_ENROLLED'))
    # Reuses positive UUID database identity checks and matching native PG tools.
    # This synthetic dump is not an encrypted production backup acceptance.
    with restored_fixture(owner,request.config.getoption('--database')) as (url,storage):
        engine=make_engine(replace(owner.state.config,database_url=url,document_storage_dir=storage))
        try:
            with make_session_factory(engine)() as db:
                restored=db.get(MfaCredential,user_id)
                assert restored.enabled and restored.last_step==step and restored.seed_ciphertext==ciphertext
                assert app.state.mfa_cipher.decrypt(user_id,restored.seed_ciphertext)==seed
                assert db.get(SecurityEvent,audit_id).action=='MFA_ENROLLED'
                assert db.get(MfaPolicy,1).required
        finally:
            engine.dispose()


def test_service_tokens_remain_separate_from_human_factor(mfa):
    client,app,owner,_=mfa
    enroll(client)
    record=create_contract(client)
    token='ohvr_synthetic_service_token_for_mfa_boundary'
    with owner.state.session_factory() as db:
        user=db.scalar(select(User).where(User.username=='admin'))
        db.add(IntegrationToken(name='Synthetic service',token_prefix=token[:16],token_hash=hash_value(token),
            created_by_id=user.id,owner_user_id=user.id,service_owner='Synthetic accountable owner',
            api_scopes='metadata',expires_at=now_utc()+timedelta(hours=1)))
        db.commit()
    assert login(client,'admin').headers['location']=='/account/mfa'
    response=client.get('/api/v2/snapshot',headers={'Authorization':'Bearer '+token})
    assert response.status_code==200 and response.json()['data'][0]['id']==record


@pytest.mark.postgresql
def test_simultaneous_enrollment_consumes_one_challenge_and_revokes_other(mfa,request):
    if request.config.getoption('--database')!='postgresql':
        pytest.skip('Actual PostgreSQL concurrent MFA serialization required')
    client,app,owner,_=mfa
    seed,csrf=start(client)
    with TestClient(app) as other:
        assert login(other,'admin').headers['location']=='/account/mfa'
        other_csrf=csrf_from(other.get('/account/mfa').text)
        code=pyotp.TOTP(seed).now()
        def submit(item):
            browser,token=item
            response=browser.post('/account/mfa',data={'csrf_token':token,'code':code},follow_redirects=False)
            return response.status_code,response.headers.get('location')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(submit,((client,csrf),(other,other_csrf))))
        assert sorted(results)==[(303,'/'),(303,'/login')]
        with owner.state.session_factory() as db:
            sessions=db.scalars(select(LoginSession).where(LoginSession.mfa_verified.is_(True))).all()
            assert len(sessions)==1


@pytest.mark.postgresql
def test_pg_mfa_credentials_policy_and_challenge_have_no_normal_data_access(mfa,request):
    if request.config.getoption('--database')!='postgresql':
        pytest.skip('Actual restricted PostgreSQL MFA/RLS boundary required')
    client,app,owner,runtime=mfa
    seed,csrf=start(client)
    cookie=client.cookies.get(COOKIE_NAME)
    with runtime_session(runtime,cookie=cookie) as db:
        assert db.scalars(text('SELECT id FROM contracts')).all()==[]
        for table in ('mfa_credentials','mfa_policy'):
            with pytest.raises(DBAPIError),db.begin_nested():db.execute(text('SELECT * FROM '+table))
        assert db.scalar(text('SELECT ohvr_security.mfa_material(:hash,NULL)'),{'hash':'0'*64}) is None
    with app.state.integration_engine.connect() as connection:
        with pytest.raises(DBAPIError):connection.execute(text("SELECT ohvr_security.mfa_material('','')"))
    response=client.post('/account/mfa',data={'csrf_token':csrf,'code':pyotp.TOTP(seed).now()},follow_redirects=False)
    assert response.status_code==303
    record=create_contract(client)
    assert client.get(f'/contracts/{record}').status_code==200
