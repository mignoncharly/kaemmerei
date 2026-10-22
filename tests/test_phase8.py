"""Frontend contracts verified on SQLite and actual restricted PostgreSQL roles."""
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
import re
import pytest
from sqlalchemy import select
from app.models import Contract, ContractTask, ContractReview, User, RecipientTeam, RecipientMembership
from app.presentation import safe_values
from tests.support import environment_context, login, create_contract, contract_payload, csrf_from, workflow_payload
from tests.runtime_support import runtime_environment


@pytest.fixture
def frontend(request):
    if request.config.getoption('--database')=='postgresql':
        with runtime_environment() as r:yield r.client,r.app,r.owner
    else:
        with environment_context('sqlite') as (client,app):yield client,app,app


class Inputs(HTMLParser):
    def __init__(self,text):
        super().__init__();self.inputs=[];self.feed(text)
    def handle_starttag(self,tag,attrs):
        if tag=='input':self.inputs.append(dict(attrs))
    def checkbox(self,name):
        return next(i for i in self.inputs if i.get('name')==name and i.get('type')=='checkbox')


def test_boolean_validation_recovery_and_no_secret_echo(frontend):
    client,app,owner=frontend;login(client,'admin')
    data=contract_payload(designation='');data.update(csrf_token=csrf_from(client.get('/contracts/new').text),automatic_renewal='0',annual_value='0')
    page=client.post('/contracts/new',data=data)
    assert page.status_code==422
    assert 'checked' not in Inputs(page.text).checkbox('automatic_renewal')
    assert 'value="0"' in page.text
    data=dict(username='state_test',role='department',department_id='1',is_active='0',can_approve='0',
        password='DO_NOT_ECHO',csrf_token=csrf_from(client.get('/admin/users/new').text))
    page=client.post('/admin/users/new',data=data)
    assert page.status_code==422 and 'DO_NOT_ECHO' not in page.text
    for field in ('is_active','can_approve'):assert 'checked' not in Inputs(page.text).checkbox(field)
    assert 'state_test' in page.text
    assert safe_values({'password':'secret','csrf_token':'secret','TOKEN':'secret','designation':'Safe','automatic_renewal':'0'})['automatic_renewal'] is False


def test_budget_dropdown_has_choices_when_running_server_has_old_context(frontend, monkeypatch):
    import app.main as main
    client, app, owner = frontend
    original_context = main.base_context
    def previous_context(*args, **kwargs):
        context = original_context(*args, **kwargs)
        context.pop('budget_assignments', None)
        return context
    # A running worker can see the updated template before reimporting Python.
    monkeypatch.setattr(main, 'base_context', previous_context)
    login(client, 'admin')
    page = client.get('/contracts/new')
    assert page.status_code == 200
    field = re.search(r'<select id="budget_assignment".*?</select>', page.text, re.S).group()
    for choice in ('Produktkonto', 'Kontostelle', 'Sachkonto'):
        assert f'<option value="{choice}"' in field


def test_html_errors_json_api_and_conflict_recovery(frontend):
    client,app,owner=frontend;login(client,'admin');cid=create_contract(client)
    response=client.get('/contracts/999999')
    assert response.status_code==404 and response.headers['content-type'].startswith('text/html')
    assert 'role="alert"' in response.text and 'Zur Übersicht' in response.text
    assert client.get('/?page=0').status_code==422
    api=client.get('/api/v1/contracts')
    assert api.status_code==401 and api.headers['content-type'].startswith('application/json')
    data=contract_payload(designation='RESTORE <script>unsafe</script>')
    data.update(csrf_token='INVALID_SECRET',password='PASSWORD_SECRET',token='TOKEN_SECRET')
    response=client.post(f'/contracts/{cid}/edit',data=data)
    assert response.status_code==403 and 'RESTORE' in response.text
    assert '&lt;script&gt;' in response.text and '<script>unsafe' not in response.text
    for secret in ('INVALID_SECRET','PASSWORD_SECRET','TOKEN_SECRET'):assert secret not in response.text
    data['csrf_token']=csrf_from(client.get('/').text);data['version']='0'
    response=client.post(f'/contracts/{cid}/edit',data=data)
    assert response.status_code==409 and 'RESTORE' in response.text
    for secret in ('PASSWORD_SECRET','TOKEN_SECRET'):assert secret not in response.text


def test_scoped_pagination_beyond_old_cap_and_export_parity(frontend):
    client,app,owner=frontend
    stamp=datetime(2026,1,1)
    with owner.state.session_factory() as db:
        for i in range(512):
            db.add(Contract(contract_number=f'PAGE-{i:04}',designation=f'Paging {i:04}',contract_type='Miete',
                relevant_date=date(2026,1,1),department_id=1 if i<507 else 2,contact_person='Dienststelle',
                created_by_id=1,updated_by_id=1,created_at=stamp,updated_at=stamp))
        db.commit()
    login(client,'kultur')
    ids=[]
    url='/?q=Paging&page_size=100&department=2'
    while url:
        response=client.get(url);assert response.status_code==200
        context=response.context;assert context['total_count']==507
        ids.extend(c.id for c in context['contracts']);url=context['next_page_url']
        if url:assert 'q=Paging' in url and 'page_size=100' in url
    assert len(ids)==len(set(ids))==507
    assert ids==sorted(ids,reverse=True)
    from zipfile import ZipFile
    from io import BytesIO
    from xml.etree import ElementTree as ET
    exported=client.get('/contracts/export.xlsx?q=Paging&department=2')
    assert exported.status_code==200
    with ZipFile(BytesIO(exported.content)) as z:
        sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        assert len(sheet.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'))==508
    assert client.get('/?page_size=101').status_code==422
    assert client.get('/?department='+'9'*100).status_code==200
    assert client.get('/?page=1000000&page_size=100').context['page']==6


def test_distinct_approval_contracts_and_csp_width_classes(frontend):
    client,app,owner=frontend;login(client,'admin');cid=create_contract(client)
    for subject in ('First','Second'):
        path=f'/contracts/{cid}/reviews'
        assert client.post(path,data=workflow_payload(client,path,{'csrf_token':csrf_from(client.get('/').text),
            'recipient':'Kämmerei','subject':subject}),follow_redirects=False).status_code==303
    assert client.get('/').context['focus_counts']['approval']==1
    assert client.get('/?focus=approval').context['total_count']==1
    edit=contract_payload();edit.update(annual_value='100',financial_direction='expense',value_basis='net',
        csrf_token=csrf_from(client.get(f'/contracts/{cid}/edit').text),version='1')
    assert client.post(f'/contracts/{cid}/edit',data=edit,follow_redirects=False).status_code==303
    response=client.get('/reports')
    assert 'style=' not in response.text and 'pct-100' in response.text
    assert "style-src 'self'" in response.headers['content-security-policy']
    assert 'unsafe-inline' not in response.headers['content-security-policy']
    assert '.pct-100{width:100%}' in client.get('/static/site.css').text
    js=client.get('/static/notifications.js').text
    assert 'setTimeout' not in js and 'data-dismiss-notice' in js


def test_personal_inbox_requires_scope_assignment_revision_and_capability(frontend):
    client,app,owner=frontend;login(client,'admin')
    own=create_contract(client);private=create_contract(client,'2')
    with owner.state.session_factory() as db:
        staff=db.scalar(select(User).where(User.username=='kultur'));staff.can_approve=True
        team=RecipientTeam(name='Synthetic inbox team',is_active=True);db.add(team);db.flush()
        db.add(RecipientMembership(team_id=team.id,user_id=staff.id))
        for cid,title in ((own,'MY_REVIEW'),(private,'PRIVATE_REVIEW')):
            db.add(ContractReview(contract_id=cid,recipient=team.name,subject=title,request_text='',result_text='',
                status='open',created_by_id=1,team_id=team.id,assigned_user_id=staff.id,content_revision=1,
                due_date=date.today()-timedelta(days=1)))
            db.add(ContractTask(contract_id=cid,title=title+'_TASK',kind='other',status='open',description='',
                assigned_user_id=staff.id,created_by_id=1,due_date=date.today()-timedelta(days=1)))
        db.commit()
    client.post('/logout',data={'csrf_token':csrf_from(client.get('/').text)});login(client,'kultur')
    response=client.get('/reviews')
    assert response.status_code==200 and 'MY_REVIEW' in response.text and 'MY_REVIEW_TASK' in response.text
    assert 'PRIVATE_REVIEW' not in response.text and 'Überfällig' in response.text
    with owner.state.session_factory() as db:
        db.scalar(select(User).where(User.username=='kultur')).can_approve=False;db.commit()
    response=client.get('/reviews')
    assert 'MY_REVIEW</a>' not in response.text and 'MY_REVIEW_TASK' in response.text


def test_archive_confirmation_and_readonly_controls(frontend):
    client,app,owner=frontend;login(client,'admin');cid=create_contract(client)
    page=client.get(f'/contracts/{cid}')
    assert 'confirm_archive' in page.text and 'Vertrag jetzt archivieren' in page.text
    data={'csrf_token':csrf_from(page.text),'version':'1','confirm_archive':'1','request_id':'browser-confirm'}
    assert client.post(f'/contracts/{cid}/archive',data=data,follow_redirects=False).status_code==303
    page=client.get(f'/contracts/{cid}')
    assert 'Archivierter Vertrag' in page.text and 'confirm_archive' not in page.text
    assert f'action="/contracts/{cid}/tasks"' not in page.text


def test_export_limit_and_ui_review_choices(frontend,monkeypatch):
    import app.main as main
    from app.presentation import review_options
    from types import SimpleNamespace
    client,app,owner=frontend;login(client,'admin')
    create_contract(client);create_contract(client)
    monkeypatch.setattr(main,'EXPORT_MAX_ROWS',1)
    response=client.get('/contracts/export.xlsx')
    assert response.status_code==413 and response.headers['content-type'].startswith('text/html')
    choices=[('open','Open'),('approved','Approved')]
    user=SimpleNamespace(id=1,role='admin')
    contract=SimpleNamespace(content_revision=2,created_by_id=1,material_actor_id=1)
    review=SimpleNamespace(content_revision=2,status='open',assigned_user_id=1,team_id=1)
    assert review_options(user,contract,review,True,choices)==[('open','Open')]
    review.status='approved'
    assert review_options(user,contract,review,True,choices)==[('open','Open')]
    user.role='department'
    assert review_options(user,contract,review,True,choices)==[]
    review.status='open';review.content_revision=1
    assert review_options(user,contract,review,True,choices)==[]


def test_tax_and_activation_controls_match_capabilities(frontend):
    client,app,owner=frontend;login(client,'kultur')
    page=client.get('/contracts/new')
    assert 'steuerliche Bewertung ist der Administration vorbehalten' in page.text
    assert re.search(r'<select[^>]*name="tax_review_status"[^>]*disabled',page.text)
    assert re.search(r'<textarea[^>]*name="tax_review_result"[^>]*readonly',page.text)
    assert re.search(r'<option[^>]*disabled[^>]*value="active"',page.text)
    assert 'name="tax_review_status" value="not_checked"' in page.text
