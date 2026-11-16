"""Real PostgreSQL operator audit boundary after non-inherited role hardening."""
from dataclasses import replace
from datetime import timedelta
import sys
import json

from cryptography.fernet import Fernet
from app.mfa_codec import SeedCipher

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app import cli
from app.config import Settings
from app.db import make_engine
from app.identity_service import audit
from app.migrations import upgrade_connection
from app.models import Department, User, MfaCredential, MfaPolicy, LoginSession, now_utc
from tests.runtime_support import runtime_environment
from tests.support import PASSWORD

pytestmark = pytest.mark.postgresql
SIGNATURE = 'ohvr_security.append_operator_audit(text,text,jsonb)'


@pytest.fixture
def hardened(request):
    if request.config.getoption('--database') != 'postgresql':
        pytest.skip('Requires real restricted PostgreSQL roles, not SQLite')
    with runtime_environment(noninherit_audit=True) as runtime:
        yield runtime


def operator(monkeypatch, runtime, *args):
    monkeypatch.setattr(cli, 'get_settings', lambda: replace(runtime.app.state.config,
        migration_database_url=runtime.owner.state.engine.url.render_as_string(hide_password=False),
        mfa_key_file=getattr(runtime, 'test_key_file', None)))
    monkeypatch.setattr(cli, 'ask_password', lambda: PASSWORD)
    monkeypatch.setattr(sys, 'argv', ['ohvr', *args])
    cli.execute()


def audit_rows(runtime):
    with runtime.owner.state.engine.begin() as connection:
        connection.exec_driver_sql('SET LOCAL ROLE ' + connection.dialect.identifier_preparer.quote(runtime.names['audit']))
        return connection.execute(text('SELECT * FROM public.identity_audit ORDER BY id')).mappings().all()


def test_bootstrap_identity_and_mfa_administration(hardened, monkeypatch, tmp_path):
    r = hardened
    with r.owner.state.engine.connect() as c:
        assert not c.scalar(text("SELECT has_table_privilege(current_user,'identity_audit','INSERT')"))
        assert c.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='identity_audit'::regclass")).one() == (True, True)
    operator(monkeypatch, r, 'add-department', 'Kämmerei')
    operator(monkeypatch, r, 'add-user', 'pilot_admin', '--role', 'admin')
    operator(monkeypatch, r, 'add-user', 'pilot_department', '--role', 'department', '--department', 'Kämmerei')
    operator(monkeypatch, r, 'change-password', 'pilot_admin')
    operator(monkeypatch, r, 'mfa-enroll-authorize', 'pilot_admin', '--reference', 'TEST-ENROLL', '--identity-verified')
    with r.owner.state.session_factory() as db:
        user = db.scalar(select(User).where(User.username == 'pilot_admin'))
        credential = db.get(MfaCredential, user.id)
        credential.enabled = True
        r.test_key_file = tmp_path / 'keys.json'
        r.test_key_file.write_text(json.dumps([Fernet.generate_key().decode()]))
        cipher = SeedCipher(r.test_key_file)
        credential.seed_ciphertext = cipher.encrypt(user.id, 'A' * 32)
        db.commit()
    operator(monkeypatch, r, 'mfa-key-rotate', '--limit', '100')
    operator(monkeypatch, r, 'mfa-recover', 'pilot_admin', '--reference', 'TEST-RECOVER', '--identity-verified')
    operator(monkeypatch, r, 'mfa-enforce', '--reference', 'TEST-ROLLOUT', '--confirm-session-revocation')
    operator(monkeypatch, r, 'disable-user', 'pilot_department')
    with r.owner.state.session_factory() as db:
        user = db.scalar(select(User).where(User.username == 'pilot_admin'))
        assert user.must_change_password
        credential = db.get(MfaCredential, user.id)
        assert not credential.enabled and credential.seed_ciphertext is None
        assert credential.authorization_expires_at > now_utc()
        assert db.get(MfaPolicy, 1).required
        assert not db.scalar(select(User.is_active).where(User.username == 'pilot_department'))
        assert not db.scalars(select(LoginSession)).all()
    rows = audit_rows(r)
    actions = [row['action'] for row in rows]
    for action in ('departments_created', 'user_created', 'user_updated',
                   'mfa_enrollment_authorized', 'mfa_recovery_authorized', 'mfa_policy_enabled'):
        assert action in actions
    for row in rows:
        assert row['principal'] == 'operator' and row['actor_id'] is None
        assert row['outcome'] == 'success' and row['correlation_id']
        assert PASSWORD not in str(row['details'])
    # Even the audit owner cannot rewrite/delete committed evidence.
    for statement in ('UPDATE identity_audit SET target=target', 'DELETE FROM identity_audit'):
        with pytest.raises(DBAPIError) as exc, r.owner.state.engine.begin() as c:
            c.exec_driver_sql('SET LOCAL ROLE ' + c.dialect.identifier_preparer.quote(r.names['audit']))
            c.exec_driver_sql(statement)
        assert exc.value.orig.sqlstate == '42501'


def test_forward_upgrade_runtime_denial_and_atomic_failure(hardened, monkeypatch):
    r = hardened
    # Recreate the deployed 0027/hardened starting point in this disposable DB.
    with r.owner.state.engine.begin() as c:
        c.exec_driver_sql('SET LOCAL ROLE ' + c.dialect.identifier_preparer.quote(r.names['audit']))
        c.exec_driver_sql('DROP FUNCTION ' + SIGNATURE)
        c.exec_driver_sql('RESET ROLE')
        c.exec_driver_sql("UPDATE alembic_version SET version_num='0027_child_read_admission'")
    with r.owner.state.engine.connect() as c:
        upgrade_connection(c)
    operator(monkeypatch, r, 'add-department', 'Forward upgrade works')
    for kind in ('web', 'integration', 'maintenance'):
        engine = make_engine(Settings(database_url=r.urls[kind]))
        try:
            with pytest.raises(DBAPIError) as exc, engine.begin() as c:
                c.exec_driver_sql("SELECT ohvr_security.append_operator_audit('forged','target','{}')")
            assert exc.value.orig.sqlstate == '42501'
        finally:
            engine.dispose()
    # Runtime denial also holds if an accidental EXECUTE grant is introduced.
    with r.owner.state.engine.begin() as c:
        c.exec_driver_sql('SET LOCAL ROLE ' + c.dialect.identifier_preparer.quote(r.names['audit']))
        c.exec_driver_sql('GRANT EXECUTE ON FUNCTION ' + SIGNATURE + ' TO ' + c.dialect.identifier_preparer.quote(r.names['web']))
    engine = make_engine(Settings(database_url=r.urls['web']))
    try:
        with pytest.raises(DBAPIError) as exc, engine.begin() as c:
            c.exec_driver_sql("SELECT ohvr_security.append_operator_audit('forged','target','{}')")
        assert exc.value.orig.sqlstate == '42501'
    finally:
        engine.dispose()
    # No direct audit INSERT grant is added to the migrator.
    with pytest.raises(DBAPIError) as exc, r.owner.state.engine.begin() as c:
        c.exec_driver_sql("INSERT INTO identity_audit(principal,action,target,details,created_at) VALUES('operator','forged','target','{}',now())")
    assert exc.value.orig.sqlstate == '42501'
    with r.owner.state.session_factory() as db:
        for name, token in (('admin', 'a' * 64), ('kultur', 'b' * 64)):
            user_id = db.scalar(select(User.id).where(User.username == name))
            db.add(LoginSession(token_hash=token, user_id=user_id, csrf_token='synthetic',
                                expires_at=now_utc() + timedelta(hours=1)))
        db.commit()
    before = len(audit_rows(r))
    # An append already executed also disappears if a later mutation fails.
    with pytest.raises(DBAPIError), r.owner.state.session_factory() as db:
        audit(db, None, 'test_rollback', 'synthetic')
        db.add(Department(name='Forward upgrade works'))
        db.commit()
    assert len(audit_rows(r)) == before
    # Force failure at the append, after the department INSERT has flushed.
    with r.owner.state.engine.begin() as c:
        migrator = c.scalar(text('SELECT current_user'))
        c.exec_driver_sql('SET LOCAL ROLE ' + c.dialect.identifier_preparer.quote(r.names['audit']))
        c.exec_driver_sql('REVOKE EXECUTE ON FUNCTION ' + SIGNATURE + ' FROM ' + c.dialect.identifier_preparer.quote(migrator))
    with pytest.raises(DBAPIError):
        operator(monkeypatch, r, 'add-department', 'Must roll back')
    for command in ('mfa-enroll-authorize', 'mfa-recover'):
        with pytest.raises(SystemExit, match='MFA administration failed'):
            operator(monkeypatch, r, command, 'admin', '--reference', 'TEST-FAIL', '--identity-verified')
    with pytest.raises(SystemExit, match='MFA administration failed'):
        operator(monkeypatch, r, 'mfa-enforce', '--reference', 'TEST-FAIL', '--confirm-session-revocation')
    with r.owner.state.session_factory() as db:
        password_hash = db.scalar(select(User.password_hash).where(User.username == 'kultur'))
    for args in (('add-user', 'rollback_user', '--role', 'reviewer'),
                 ('change-password', 'kultur'), ('disable-user', 'kultur')):
        with pytest.raises(DBAPIError):
            operator(monkeypatch, r, *args)
    with r.owner.state.session_factory() as db:
        assert db.scalar(select(Department).where(Department.name == 'Must roll back')) is None
        admin = db.scalar(select(User).where(User.username == 'admin'))
        assert db.get(MfaCredential, admin.id) is None
        assert not admin.must_change_password
        assert not db.get(MfaPolicy, 1).required
        assert db.get(LoginSession, 'a' * 64) is not None
        assert db.get(LoginSession, 'b' * 64) is not None
        assert db.scalar(select(User).where(User.username == 'rollback_user')) is None
        kultur = db.scalar(select(User).where(User.username == 'kultur'))
        assert kultur.is_active and not kultur.must_change_password and kultur.password_hash == password_hash
    assert len(audit_rows(r)) == before
