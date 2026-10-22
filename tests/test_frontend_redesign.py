"""Presentation regression tests: real requests, permissions and rendered HTML.

These do not claim visual or screen-reader acceptance.
"""
from html.parser import HTMLParser
import re
import pytest
from sqlalchemy import select
from app.models import User
from tests.support import login, create_contract, csrf_from

class Markup(HTMLParser):
    VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self, text):
        super().__init__(); self.stack=[]; self.errors=[]; self.ids=[]; self.inputs=[]; self.labels=[]; self.feed(text)
        assert not self.stack, self.stack
        assert not self.errors, self.errors
        assert len(set(self.ids)) == len(self.ids), 'Duplicate HTML IDs'
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag not in self.VOID: self.stack.append(tag)
        if attrs.get('id'): self.ids.append(attrs['id'])
        if tag=='label' and attrs.get('for'): self.labels.append(attrs['for'])
        if tag in ('input','select','textarea') and attrs.get('type')!='hidden':
            self.inputs.append((attrs, 'label' in self.stack))
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID: self.handle_endtag(tag)
    def handle_endtag(self, tag):
        if tag in self.VOID: return
        if not self.stack or self.stack[-1]!=tag: self.errors.append((tag,self.stack[-3:]))
        else: self.stack.pop()
    def labels_present(self):
        for attrs, wrapped in self.inputs:
            assert wrapped or attrs.get('aria-label') or attrs.get('id') in self.labels, attrs

@pytest.mark.parametrize('username', ['admin','kultur','bau','pruefer'])
def test_shell_roles_scoped_dashboard_and_errors(environment, username):
    client,app=environment;login(client,'admin')
    own=create_contract(client,designation='VISIBLE_KULTUR')
    foreign=create_contract(client,'2',designation='PRIVATE_BAU')
    client.cookies.clear();login(client,username)
    response=client.get('/dashboard')
    assert response.status_code==200
    assert 'class="sidebar"' in response.text
    assert ('href="/admin/users"' in response.text)==(username=='admin')
    assert ('href="/contracts/new"' in response.text)==(username!='pruefer')
    assert len(response.context['contracts'])<=6
    if username=='kultur':
        assert 'PRIVATE_BAU' not in response.text
        assert response.context['total_count']==1
        assert client.get(f'/contracts/{foreign}').status_code==404
    assert ('href="/admin/users"' in client.get('/not-found').text)==(username=='admin')
    error=client.get('/contracts/999999')
    assert error.status_code==404 and 'class="sidebar"' in error.text
    Markup(error.text)
    if username!='admin': assert client.get('/admin/users').status_code==403
    for path in ['/dashboard','/','/reviews','/reports','/account/password']:
        page=client.get(path);assert page.status_code==200
        markup=Markup(page.text);markup.labels_present()
        assert ' style=' not in page.text
        assert "script-src 'self'" in page.headers['content-security-policy']

def test_admin_pages_forms_and_recovery_have_valid_markup(environment):
    client,app=environment;login(client,'admin');cid=create_contract(client)
    for path in ['/contracts/new',f'/contracts/{cid}',f'/contracts/{cid}/edit',
                 '/admin/users','/admin/users/new','/admin/users/2/edit','/admin/identities','/admin/integrations']:
        response=client.get(path);assert response.status_code==200
        markup=Markup(response.text);markup.labels_present()
    response=client.post('/admin/integrations',data={
        'csrf_token':csrf_from(client.get('/admin/integrations').text),
        'name':'Recover application', 'service_owner':'Recover service','owner_user_id':'1',
        'api_profile':'v2','expires_in':'never','capability':['metadata','finance']})
    assert response.status_code==422
    assert 'value="Recover application"' in response.text
    assert 'value="Recover service"' in response.text
    assert re.search(r'value="finance"\s+checked',response.text)
    Markup(response.text).labels_present()

def test_initial_password_and_guest_errors_have_auth_layout(environment):
    client,app=environment
    assert 'class="sidebar"' not in client.get('/login').text
    assert 'class="auth-layout"' in client.get('/unknown').text
    with app.state.session_factory() as db:
        user=db.scalar(select(User).where(User.username=='kultur'));user.must_change_password=True;db.commit()
    login(client,'kultur')
    page=client.get('/account/password')
    assert page.status_code==200 and 'class="sidebar"' not in page.text
    Markup(page.text).labels_present()

def test_unexpected_failure_has_sanitized_html_and_api_json(environment):
    from fastapi.testclient import TestClient
    client,app=environment
    @app.get('/__synthetic_failure')
    def failure(): raise RuntimeError('DO_NOT_EXPOSE_INTERNAL_DETAIL')
    @app.get('/api/__synthetic_failure')
    def api_failure(): raise RuntimeError('DO_NOT_EXPOSE_INTERNAL_DETAIL')
    with TestClient(app,raise_server_exceptions=False) as test:
        response=test.get('/__synthetic_failure')
        assert response.status_code==500
        assert 'DO_NOT_EXPOSE_INTERNAL_DETAIL' not in response.text
        assert 'Technischer Fehler' in response.text
        assert 'no-store' in response.headers['cache-control']
        Markup(response.text)
        response=test.get('/api/__synthetic_failure')
        assert response.status_code==500 and response.json()=={'detail':'Internal server error'}
