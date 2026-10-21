"""Phase 2 regressions, executed with migrated SQLite and real PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select, text

from app.authorization import contract_query, load_child
from app.identity_service import save_user
from app.models import (ContactIdentity, Contract, ContractReview, Department, IdentityAudit, IntegrationToken, LoginSession,
                        RecipientMembership, RecipientTeam, Revision, User)
from app.security import COOKIE_NAME, hash_value, ph
from tests.support import PASSWORD, contract_payload, create_contract, csrf_from, login


def switch(client, username):
    page = client.get('/')
    if page.status_code == 200:
        client.post('/logout', data={'csrf_token': csrf_from(page.text)})
    assert login(client, username).status_code == 303


def csrf(client, path='/'):
    return csrf_from(client.get(path).text)


def review_fixture(client, app, department='1'):
    assert login(client, 'admin').status_code == 303
    record = create_contract(client, department)
    assert client.post(f'/contracts/{record}/reviews', data={'csrf_token': csrf(client),
        'recipient': 'Kämmerei', 'subject': 'Phase 2 explicit assignment'}, follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        review_id = db.scalar(select(ContractReview.id))
    return record, review_id


def user_values(username, role='reviewer', **kwargs):
    return dict(username=username, role=role, department_id='', is_active='1', password='', **kwargs)


def test_reviewer_requires_capability_membership_assignment_and_existing_read_access(environment):
    client, app = environment
    record, review_id = review_fixture(client, app)
    path = f'/contracts/{record}/reviews/{review_id}'
    switch(client, 'pruefer')
    assert client.get(f'/contracts/{record}').status_code == 200
    assert 'Prüfstatus / Rückmeldung bearbeiten' not in client.get(f'/contracts/{record}').text
    decision = {'csrf_token': csrf(client), 'status': 'approved', 'result_text': 'Explicitly reviewed'}
    assert client.post(path, data=decision).status_code == 403
    with app.state.session_factory() as db:
        account = db.scalar(select(User).where(User.username == 'pruefer'))
        account.can_approve = True
        team = RecipientTeam(name='Explicit team')
        db.add(team)
        db.flush()
        team_id, user_id = team.id, account.id
        db.add(RecipientMembership(team_id=team_id, user_id=user_id))
        db.commit()
    assert client.post(path, data=decision).status_code == 403  # Capability + membership are insufficient.
    assert 'Phase 2 explicit assignment' not in client.get('/reviews').text
    switch(client, 'admin')
    assignment = {'csrf_token': csrf(client), 'team_id': str(team_id), 'user_id': str(user_id)}
    assert client.post(path + '/assignment', data=assignment, follow_redirects=False).status_code == 303
    switch(client, 'pruefer')
    assert 'Phase 2 explicit assignment' in client.get('/reviews').text
    decision['csrf_token'] = csrf(client)
    assert client.post(path, data=decision, follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        assert db.get(ContractReview, review_id).status == 'approved'
        event = db.scalar(select(IdentityAudit).where(IdentityAudit.action == 'review_decided'))
        assert event.actor_id == user_id and event.details['team_id'] == team_id
        db.delete(db.get(RecipientMembership, (team_id, user_id)))
        db.commit()
    assert client.post(path, data=decision).status_code == 403  # Revocation checked server-side.


def test_assignment_never_grants_cross_department_access_and_admin_can_clear(environment):
    client, app = environment
    record, review_id = review_fixture(client, app, '2')
    with app.state.session_factory() as db:
        account = db.scalar(select(User).where(User.username == 'kultur'))
        account.can_approve = True
        team = RecipientTeam(name='Scope test')
        db.add(team)
        db.flush()
        db.add(RecipientMembership(team_id=team.id, user_id=account.id))
        team_id, user_id = team.id, account.id
        db.commit()
    path = f'/contracts/{record}/reviews/{review_id}'
    assert client.post(path + '/assignment', data={'csrf_token': csrf(client), 'team_id': team_id,
        'user_id': user_id}).status_code == 422
    # Even a stale/manually imported assignment cannot bypass parent authorization.
    with app.state.session_factory() as db:
        review = db.get(ContractReview, review_id)
        review.team_id, review.assigned_user_id = team_id, user_id
        db.commit()
    switch(client, 'kultur')
    assert client.get(f'/contracts/{record}').status_code == 404
    assert client.post(path, data={'csrf_token': csrf(client), 'status': 'approved', 'result_text': 'Denied'}).status_code == 404
    assert 'Phase 2 explicit assignment' not in client.get('/reviews').text
    switch(client, 'admin')
    assert client.post(path + '/assignment', data={'csrf_token': csrf(client), 'team_id': '',
        'user_id': ''}, follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        assert db.get(ContractReview, review_id).assigned_user_id is None


def test_department_admin_suspension_revokes_sessions_and_reactivation_preserves_records(environment):
    from fastapi.testclient import TestClient
    client, app = environment
    login(client, 'admin')
    record = create_contract(client)
    with TestClient(app) as staff:
        login(staff, 'kultur')
        with app.state.session_factory() as db:
            account = db.scalar(select(User).where(User.username == 'kultur'))
            staff_id = account.id
            raw = 'ohvr_' + 'L' * 32
            db.add(IntegrationToken(name='Lifecycle', token_prefix=raw[:16], token_hash=hash_value(raw),
                                    department_id=1, created_by_id=1))
            db.commit()
        headers = {'Authorization': 'Bearer ' + raw}
        assert client.get('/api/v1/contracts', headers=headers).status_code == 200
        path = '/admin/identities/departments/1'
        assert client.post(path, data={'csrf_token': csrf(client), 'name': 'Kultur renamed'}, follow_redirects=False).status_code == 303
        assert staff.get('/', follow_redirects=False).status_code == 303
        assert client.get('/api/v1/contracts', headers=headers).status_code == 401
        with app.state.session_factory() as db:
            assert db.scalar(select(func.count()).select_from(LoginSession).where(LoginSession.user_id == staff_id)) == 0
            assert db.get(Contract, record).department_id == 1
            assert db.get(Department, 1).name == 'Kultur renamed'
            assert db.scalar(select(IdentityAudit).where(IdentityAudit.action == 'departments_updated')) is not None
        assert client.post(path, data={'csrf_token': csrf(client), 'name': 'Kultur renamed', 'is_active': '1'},
                           follow_redirects=False).status_code == 303
        assert staff.get('/', follow_redirects=False).status_code == 303  # Old sessions never resurrect.
        assert login(staff, 'kultur').status_code == 303
        assert staff.get(f'/contracts/{record}').status_code == 200
        assert client.get('/api/v1/contracts', headers=headers).status_code == 200


def test_password_change_requires_old_password_csrf_and_rotates_sessions_without_secret_audit(environment):
    from fastapi.testclient import TestClient
    client, app = environment
    login(client, 'kultur')
    with TestClient(app) as other:
        login(other, 'kultur')
        old_cookie = client.cookies.get(COOKIE_NAME)
        new_password = 'Phase2-New-Synthetic-Password-2026'
        values = dict(csrf_token=csrf(client, '/account/password'), current_password='incorrect',
                      new_password=new_password, confirm_password=new_password)
        assert client.post('/account/password', data=values).status_code == 422
        values['current_password'] = PASSWORD
        values['csrf_token'] = 'invalid'
        assert client.post('/account/password', data=values).status_code == 403
        values['csrf_token'] = csrf(client, '/account/password')
        assert client.post('/account/password', data=values, follow_redirects=False).status_code == 303
        assert client.cookies.get(COOKIE_NAME) != old_cookie
        assert other.get('/', follow_redirects=False).status_code == 303
        assert client.get('/').status_code == 200
        with app.state.session_factory() as db:
            event = db.scalar(select(IdentityAudit).where(IdentityAudit.action == 'password_changed'))
            assert new_password not in str(event.details) and PASSWORD not in str(event.details)
            assert db.get(LoginSession, hash_value(old_cookie)) is None


def test_admin_recovery_forces_change_and_immutable_username_and_shared_validation(environment):
    client, app = environment
    login(client, 'admin')
    with app.state.session_factory() as db:
        target_id = db.scalar(select(User.id).where(User.username == 'pruefer'))
    path = f'/admin/users/{target_id}/edit'
    values = user_values('forged_rename')
    values['csrf_token'] = csrf(client)
    assert client.post(path, data=values).status_code == 422
    values = user_values('pruefer')
    values.update(csrf_token=csrf(client), password='Recovery-Synthetic-Password-2026', can_approve='1')
    assert client.post(path, data=values, follow_redirects=False).status_code == 303
    switch(client, 'admin')
    client.post('/logout', data={'csrf_token': csrf(client)})
    assert login(client, 'pruefer', values['password']).status_code == 303
    assert client.get('/', follow_redirects=False).headers['location'] == '/account/password'
    assert client.get('/contracts/1', follow_redirects=False).headers['location'] == '/account/password'
    assert client.get('/account/password').status_code == 200
    new = 'Replaced-Recovery-Synthetic-2026'
    changed = dict(csrf_token=csrf(client, '/account/password'), current_password=values['password'],
                   new_password=new, confirm_password=new)
    assert client.post('/account/password', data=changed, follow_redirects=False).status_code == 303
    assert client.get('/').status_code == 200
    with app.state.session_factory() as db:
        assert db.get(User, target_id).username == 'pruefer'
        assert not db.get(User, target_id).must_change_password


def test_last_admin_protection_serializes_concurrent_writers(environment):
    _client, app = environment
    with app.state.session_factory() as db:
        first = db.scalar(select(User).where(User.username == 'admin'))
        second = User(username='second_admin', role='admin', password_hash=first.password_hash)
        db.add(second)
        db.commit()
        targets = [(first.id, first.username), (second.id, second.username)]
    gate = Barrier(2)
    def disable(item):
        user_id, name = item
        gate.wait(timeout=10)
        with app.state.session_factory() as db:
            try:
                values = user_values(name, role='admin')
                values['is_active'] = '0'
                save_user(db, values, user_id=user_id)
                db.commit()
                return 'updated'
            except ValueError:
                db.rollback()
                return 'denied'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(disable, targets)) == ['denied', 'updated']
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(User).where(User.role == 'admin', User.is_active.is_(True))) == 1


@pytest.mark.parametrize('role', ['kultur', 'pruefer', 'bau'])
def test_identity_administration_requires_admin_and_csrf(environment, role):
    client, app = environment
    login(client, role)
    assert client.get('/admin/identities').status_code == 403
    for path in ('/admin/identities/departments/1', '/admin/identities/contacts/0',
                 '/admin/identities/teams/0', '/admin/recipient-memberships'):
        assert client.post(path, data={'csrf_token': csrf(client), 'name': 'Forbidden'}).status_code == 403
    switch(client, 'admin')
    assert client.get('/admin/identities').status_code == 200
    assert client.post('/admin/identities/departments/1', data={'name': 'No CSRF'}).status_code == 403
    assert client.post('/admin/identities/contacts/0', data={'csrf_token': csrf(client), 'name': 'Bad file'},
                       files={'user_id': ('unexpected.txt', b'not-an-identity', 'text/plain')}).status_code == 400


def test_catalog_scoping_active_state_stable_scope_and_legacy_names(environment):
    client, app = environment
    login(client, 'admin')
    record = create_contract(client, '2', 'Legacy names preserved')
    with app.state.session_factory() as db:
        db.get(Contract, record).contact_person = 'PRIVATE_B_CATALOG'
        db.commit()
    for name, department in [('OWN_A_CATALOG', '1'), ('PRIVATE_B_CATALOG', '2'), ('GLOBAL_REFERENCE', '')]:
        assert client.post('/admin/identities/contacts/0', data={'csrf_token': csrf(client), 'name': name,
            'department_id': department, 'is_active': '1'}, follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        private_id = db.scalar(select(ContactIdentity.id).where(ContactIdentity.display_name == 'PRIVATE_B_CATALOG'))
    assert client.post(f'/admin/identities/contacts/{private_id}', data={'csrf_token': csrf(client),
        'name': 'PRIVATE_B_CATALOG', 'department_id': '', 'is_active': '1'}).status_code == 422
    switch(client, 'kultur')
    page = client.get('/contracts/new').text
    assert 'OWN_A_CATALOG' in page and 'GLOBAL_REFERENCE' in page and 'PRIVATE_B_CATALOG' not in page
    switch(client, 'admin')
    with app.state.session_factory() as db:
        own_id = db.scalar(select(ContactIdentity.id).where(ContactIdentity.display_name == 'OWN_A_CATALOG'))
    assert client.post(f'/admin/identities/contacts/{own_id}', data={'csrf_token': csrf(client),
        'name': 'OWN_A_CATALOG', 'department_id': '1'}, follow_redirects=False).status_code == 303
    switch(client, 'kultur')
    assert 'OWN_A_CATALOG' not in client.get('/contracts/new').text
    payload = contract_payload()
    payload.update(csrf_token=csrf(client), contact_person='OWN_A_CATALOG')
    assert client.post('/contracts/new', data=payload).status_code == 422
    with app.state.session_factory() as db:
        assert db.get(Contract, record).contact_person == 'PRIVATE_B_CATALOG'
        assert db.get(Contract, record).department_id == 2


def test_cli_uses_shared_policy_audit_and_last_admin_guard(environment, monkeypatch, capsys):
    from app import cli
    client, app = environment
    monkeypatch.setattr(cli, 'get_settings', lambda: app.state.config)
    monkeypatch.setattr(cli, 'getpass', lambda _prompt: 'Synthetic-CLI-Temporary-2026')
    monkeypatch.setattr('sys.argv', ['ohvr', 'add-user', 'Cli.New', '--role', 'reviewer'])
    cli.main()
    with app.state.session_factory() as db:
        created = db.scalar(select(User).where(User.username == 'cli.new'))
        assert created.must_change_password and not created.can_approve and created.department_id is None
        assert db.scalar(select(IdentityAudit).where(IdentityAudit.target == f'user:{created.id}')).principal == 'operator'
    monkeypatch.setattr('sys.argv', ['ohvr', 'disable-user', 'admin'])
    with pytest.raises(SystemExit, match='letzte aktive Administrator'):
        cli.main()
    monkeypatch.setattr('sys.argv', ['ohvr', 'add-user', 'bad/name', '--role', 'reviewer'])
    with pytest.raises(SystemExit, match='Benutzername'):
        cli.main()
    monkeypatch.setattr('sys.argv', ['ohvr', 'add-user', 'inconsistent', '--role', 'reviewer', '--department', 'Kultur'])
    with pytest.raises(SystemExit, match='Nur Fachbereichsnutzer'):
        cli.main()
    assert 'Synthetic-CLI-Temporary-2026' not in capsys.readouterr().out


def test_new_web_accounts_are_forced_to_change_and_permission_changes_revoke_sessions(environment):
    from fastapi.testclient import TestClient
    client, app = environment
    login(client, 'admin')
    new_values = user_values('new_reviewer')
    new_values.update(csrf_token=csrf(client), password='Synthetic-Web-Initial-2026')
    assert client.post('/admin/users/new', data=new_values, follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        created = db.scalar(select(User).where(User.username == 'new_reviewer'))
        assert created.must_change_password and not created.can_approve
        reviewer_id = db.scalar(select(User.id).where(User.username == 'pruefer'))
    with TestClient(app) as reviewer:
        login(reviewer, 'pruefer')
        values = user_values('pruefer', can_approve='1')
        values['csrf_token'] = csrf(client)
        assert client.post(f'/admin/users/{reviewer_id}/edit', data=values, follow_redirects=False).status_code == 303
        assert reviewer.get('/', follow_redirects=False).status_code == 303
        assert login(reviewer, 'pruefer').status_code == 303
        assert 'Explizite Freigabefähigkeit' in client.get(f'/admin/users/{reviewer_id}/edit').text


def test_team_membership_admin_routes_revoke_sessions_and_suspend_decision(environment):
    from fastapi.testclient import TestClient
    client, app = environment
    record, review_id = review_fixture(client, app)
    assert client.post('/admin/identities/teams/0', data={'csrf_token': csrf(client), 'name': 'Maintained team',
        'is_active': '1'}, follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        team_id = db.scalar(select(RecipientTeam.id))
        target = db.scalar(select(User).where(User.username == 'pruefer'))
        target.can_approve = True
        target_id = target.id
        db.commit()
    with TestClient(app) as reviewer:
        login(reviewer, 'pruefer')
        data = {'csrf_token': csrf(client), 'team_id': team_id, 'user_id': target_id, 'is_active': '1'}
        assert client.post('/admin/recipient-memberships', data=data, follow_redirects=False).status_code == 303
        assert reviewer.get('/', follow_redirects=False).status_code == 303
        path = f'/contracts/{record}/reviews/{review_id}'
        assert client.post(path + '/assignment', data={'csrf_token': csrf(client), 'team_id': team_id,
            'user_id': target_id}, follow_redirects=False).status_code == 303
        login(reviewer, 'pruefer')
        assert 'Phase 2 explicit assignment' in reviewer.get('/reviews').text
        assert client.post(f'/admin/identities/teams/{team_id}', data={'csrf_token': csrf(client),
            'name': 'Maintained team'}, follow_redirects=False).status_code == 303
        assert reviewer.get('/', follow_redirects=False).status_code == 303
        login(reviewer, 'pruefer')
        assert 'Phase 2 explicit assignment' not in reviewer.get('/reviews').text
        assert reviewer.post(path, data={'csrf_token': csrf(reviewer), 'status': 'approved',
            'result_text': 'Should be denied'}).status_code == 403
        data.pop('is_active')
        data['csrf_token'] = csrf(client)
        assert client.post('/admin/recipient-memberships', data=data, follow_redirects=False).status_code == 303
        with app.state.session_factory() as db:
            assert db.get(RecipientMembership, (team_id, target_id)) is None


@pytest.mark.parametrize('new,confirm', [('short', 'short'), ('Matching-Enough-Password-2026', 'different'), (PASSWORD, PASSWORD)])
def test_password_policy_failures_do_not_revoke_or_mutate(environment, new, confirm):
    client, app = environment
    login(client, 'kultur')
    before = client.cookies.get(COOKIE_NAME)
    result = client.post('/account/password', data={'csrf_token': csrf(client, '/account/password'),
        'current_password': PASSWORD, 'new_password': new, 'confirm_password': confirm})
    assert result.status_code == 422
    assert client.cookies.get(COOKIE_NAME) == before
    with app.state.session_factory() as db:
        assert db.get(LoginSession, hash_value(before)) is not None
        assert db.scalar(select(func.count()).select_from(IdentityAudit)) == 0


def test_existing_inactive_contact_display_is_preserved_on_unrelated_edit(environment):
    client, app = environment
    login(client, 'admin')
    record = create_contract(client)
    with app.state.session_factory() as db:
        db.add(ContactIdentity(display_name='Dienststelle', department_id=1, scope_key=1, is_active=False))
        db.commit()
    values = contract_payload(designation='Unrelated edit preserves identity snapshot')
    values.update(csrf_token=csrf(client), version='1')
    assert client.post(f'/contracts/{record}/edit', data=values, follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        assert db.get(Contract, record).contact_person == 'Dienststelle'


def test_populated_phase2_migration_preserves_private_labels_and_never_grants_approval(request):
    from datetime import date, datetime
    from pathlib import Path
    from sqlalchemy import MetaData, Table
    from app.config import Settings
    from app.db import make_engine
    from app.migrations import upgrade_connection
    from tests.support import disposable_database, scratch_directory
    with scratch_directory('ohvr-phase2-migration-') as directory:
        with disposable_database(request.config.getoption('--database'), Path(directory)) as target:
            engine = make_engine(Settings(database_url=target))
            try:
                with engine.connect() as connection:
                    upgrade_connection(connection, '0013_integration_tokens')
                    users = Table('users', MetaData(), autoload_with=connection)
                    connection.execute(Department.__table__.insert(), [{'id': 1, 'name': 'Legacy A'}, {'id': 2, 'name': 'Legacy B'}])
                    stamp = datetime(2026, 1, 1)
                    connection.execute(users.insert(), dict(id=1, username='legacy_reviewer', role='reviewer',
                        password_hash='synthetic-not-authenticatable', is_active=True, created_at=stamp))
                    connection.execute(Contract.__table__.insert(), dict(id=1, contract_number='LEGACY-1',
                        designation='Preserved legacy', contract_type='Miete', relevant_date=date(2026,1,1),
                        department_id=2, contact_person='PRIVATE_LEGACY_B', deputy_contact_person='DEPUTY_LEGACY_B',
                        created_by_id=1, updated_by_id=1, created_at=stamp, updated_at=stamp))
                    reviews = Table('contract_reviews', MetaData(), autoload_with=connection)
                    connection.execute(reviews.insert(), dict(id=1, contract_id=1, recipient='Kämmerei',
                        subject='Legacy review', status='open', created_by_id=1, created_at=stamp, updated_at=stamp))
                    connection.commit()
                    upgrade_connection(connection)
                    assert connection.scalar(text('SELECT can_approve FROM users WHERE id=1')) is False or connection.scalar(text('SELECT can_approve FROM users WHERE id=1')) == 0
                    assert connection.scalar(text('SELECT must_change_password FROM users WHERE id=1')) in (False, 0)
                    row = connection.execute(text('SELECT team_id, assigned_user_id FROM contract_reviews WHERE id=1')).one()
                    assert tuple(row) == (None, None)
                    names = connection.execute(text('SELECT display_name,department_id,scope_key FROM contact_identities ORDER BY display_name')).all()
                    assert {tuple(row) for row in names} == {('PRIVATE_LEGACY_B', 2, 2), ('DEPUTY_LEGACY_B', 2, 2)}
                    assert connection.scalar(text('SELECT contact_person FROM contracts WHERE id=1')) == 'PRIVATE_LEGACY_B'
                    connection.commit()
                    upgrade_connection(connection)
            finally:
                engine.dispose()


def test_password_change_current_password_challenge_is_rate_limited(environment):
    client, app = environment
    login(client, 'kultur')
    values = dict(csrf_token=csrf(client, '/account/password'), current_password='incorrect',
                  new_password='Synthetic-Password-Ratelimit-2026', confirm_password='Synthetic-Password-Ratelimit-2026')
    for _ in range(8):
        assert client.post('/account/password', data=values).status_code == 422
    assert client.post('/account/password', data=values).status_code == 429
    assert client.get('/').status_code == 200
    with app.state.session_factory() as db:
        events = db.scalars(select(IdentityAudit).where(IdentityAudit.action == 'password_change_denied')).all()
        assert len(events) == 8
        assert all('incorrect' not in str(event.details) for event in events)


def test_admin_can_suspend_user_in_inactive_department_without_moving_identity(environment):
    client, app = environment
    login(client, 'admin')
    with app.state.session_factory() as db:
        user_id = db.scalar(select(User.id).where(User.username == 'kultur'))
        db.get(Department, 1).is_active = False
        db.commit()
    page = client.get(f'/admin/users/{user_id}/edit')
    assert page.status_code == 200 and '<option value="1"' in page.text
    values = user_values('kultur', role='department')
    values.update(csrf_token=csrf(client), is_active='0', department_id='1')
    assert client.post(f'/admin/users/{user_id}/edit', data=values, follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        account = db.get(User, user_id)
        assert not account.is_active and account.department_id == 1
