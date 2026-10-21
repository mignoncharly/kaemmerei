"""Application security acceptance, run on either explicitly selected backend."""
from sqlalchemy import select

from app.excel import read_xlsx
from app.models import Contract, ContractDocument, ContractReview, Department, IntegrationToken, Revision
from app.security import hash_value
from tests.support import contract_payload, create_contract, csrf_from, login


def logout(client):
    client.post('/logout', data={'csrf_token': csrf_from(client.get('/').text)})


def test_metadata_and_indirect_references_remain_department_scoped(environment):
    client, app = environment
    login(client, 'admin')
    own = create_contract(client, '1', 'VISIBLE_OWN')
    private = create_contract(client, '2', 'PRIVATE_DESIGNATION_B')
    token = csrf_from(client.get('/').text)
    assert client.post(f'/contracts/{private}/documents', data={'csrf_token': token},
                       files={'documents': ('PRIVATE_FILENAME_B.pdf', b'%PDF-1.4\nprivate', 'application/pdf')},
                       follow_redirects=False).status_code == 303
    assert client.post(f'/contracts/{private}/reviews', data={'csrf_token': token,
                       'recipient': 'Kämmerei', 'subject': 'PRIVATE_REVIEW_B'},
                       follow_redirects=False).status_code == 303
    raw = 'ohvr_' + 'M' * 32
    with app.state.session_factory() as db:
        contract = db.get(Contract, private)
        contract.contract_type = 'PRIVATE_TYPE_B'
        contract.contact_person = 'PRIVATE_CONTACT_B'
        contract.deputy_contact_person = 'PRIVATE_DEPUTY_B'
        document_id = db.scalar(select(ContractDocument.id))
        db.add(IntegrationToken(name='Acceptance', token_prefix=raw[:16], token_hash=hash_value(raw),
                                department_id=1, created_by_id=1))
        db.commit()
    logout(client)
    login(client, 'kultur')
    for path in ('/', '/?q=PRIVATE', '/?department=2', '/?contract_type=PRIVATE_TYPE_B', '/reports'):
        response = client.get(path)
        assert response.status_code == 200
        # A supplied search value may be echoed; stored private choices must not be populated.
        if 'PRIVATE_TYPE_B' not in path:
            assert 'PRIVATE_TYPE_B' not in response.text
        for secret in ('PRIVATE_DESIGNATION_B', 'PRIVATE_CONTACT_B', 'PRIVATE_DEPUTY_B',
                       'PRIVATE_FILENAME_B', 'PRIVATE_REVIEW_B'):
            assert secret not in response.text
    assert client.get(f'/contracts/{private}').status_code == 404
    assert client.get(f'/contracts/{private}/documents/{document_id}').status_code == 404
    assert client.get(f'/contracts/{own}/documents/{document_id}').status_code == 404
    exported = client.get('/contracts/export.xlsx')
    assert exported.status_code == 200
    assert 'PRIVATE_DESIGNATION_B' not in str(read_xlsx(exported.content))
    headers = {'Authorization': 'Bearer ' + raw}
    response = client.get('/api/v1/contracts', headers=headers)
    assert response.status_code == 200
    assert {item['id'] for item in response.json()['data']} == {own}
    assert 'PRIVATE_' not in response.text
    for parent in (own, private):
        assert client.get(f'/api/v1/contracts/{parent}/documents/{document_id}', headers=headers).status_code == 404


def test_archived_review_rejection_preserves_state_and_history(environment):
    client, app = environment
    login(client, 'admin')
    record = create_contract(client)
    csrf = csrf_from(client.get('/').text)
    assert client.post(f'/contracts/{record}/reviews', data={'csrf_token': csrf,
                       'recipient': 'Kämmerei', 'subject': 'Acceptance'}, follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        review_id = db.scalar(select(ContractReview.id))
    path = f'/contracts/{record}/reviews/{review_id}'
    decision = {'csrf_token': csrf, 'status': 'approved', 'result_text': 'Before archival'}
    assert client.post(path, data=decision, follow_redirects=False).status_code == 303
    assert client.post(f'/contracts/{record}/archive', data={'csrf_token': csrf, 'version': 1},
                       follow_redirects=False).status_code == 303
    with app.state.session_factory() as db:
        before = db.get(ContractReview, review_id)
        snapshot = (before.status, before.result_text, before.updated_at, before.updated_by_id)
        history = list(db.scalars(select(Revision.id).order_by(Revision.id)))
    for user in ('admin', 'pruefer'):
        if user == 'pruefer':
            logout(client)
            login(client, user)
        decision.update(csrf_token=csrf_from(client.get('/').text), result_text='Forbidden after archive')
        assert client.post(path, data=decision, follow_redirects=False).status_code == 409
    with app.state.session_factory() as db:
        after = db.get(ContractReview, review_id)
        assert (after.status, after.result_text, after.updated_at, after.updated_by_id) == snapshot
        assert list(db.scalars(select(Revision.id).order_by(Revision.id))) == history


def test_department_deactivation_revokes_sessions_login_and_scoped_tokens(environment):
    client, app = environment
    login(client, 'admin')
    record = create_contract(client)
    raw = 'ohvr_' + 'D' * 32
    with app.state.session_factory() as db:
        db.add(IntegrationToken(name='Department', token_prefix=raw[:16], token_hash=hash_value(raw),
                                department_id=1, created_by_id=1))
        db.commit()
    headers = {'Authorization': 'Bearer ' + raw}
    assert client.get('/api/v1/contracts', headers=headers).status_code == 200
    logout(client)
    assert login(client, 'kultur').status_code == 303
    csrf = csrf_from(client.get('/').text)
    with app.state.session_factory() as db:
        db.get(Department, 1).is_active = False
        db.commit()
    for path in ('/', f'/contracts/{record}', '/reports', '/contracts/export.xlsx'):
        assert client.get(path, follow_redirects=False).status_code == 303
    values = contract_payload(designation='Unauthorized inactive edit')
    values.update(csrf_token=csrf, version='1')
    for path in (f'/contracts/{record}/edit', f'/contracts/{record}/archive',
                 f'/contracts/{record}/reviews', f'/contracts/{record}/documents'):
        assert client.post(path, data=values, follow_redirects=False).status_code == 303
    assert login(client, 'kultur').status_code == 401
    for path in ('/api/v1/contracts', '/api/v1/departments', f'/api/v1/contracts/{record}/documents/1'):
        assert client.get(path, headers=headers).status_code == 401
    # Explicit global roles are independent of department membership.
    assert login(client, 'admin').status_code == 303
    assert client.get(f'/contracts/{record}').status_code == 200
    logout(client)
    assert login(client, 'bau').status_code == 303
    assert client.get('/').status_code == 200
    with app.state.session_factory() as db:
        assert db.get(Contract, record).version == 1

