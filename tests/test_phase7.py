"""Recorded financial history, calendar boundaries and strict create-only XLSX."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile, ZIP_DEFLATED
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, DBAPIError
from app.dates import add_months, calculate_next_end_date, calculate_notice_deadline, contract_dates
from app.excel import make_xlsx, read_xlsx, excel_date
from app.financial import aggregate, historical_groups
from app.models import Contract, Revision, User
from tests.support import environment_context, login, create_contract, csrf_from, contract_payload
from tests.runtime_support import runtime_environment


@pytest.fixture
def finance(request):
    if request.config.getoption('--database') == 'postgresql':
        with runtime_environment() as r:
            yield r.client, r.app, r.owner
    else:
        with environment_context('sqlite') as (client, app):
            yield client, app, app


def workbook(**overrides):
    row = dict(designation='Synthetic import', contract_type='Miete', relevant_date='2026-01-10',
        contact_person='Dienststelle', department='Kultur', status='draft')
    row.update(overrides)
    return make_xlsx(list(row), [list(row.values())])


def upload(client, data):
    return client.post('/contracts/import', data={'csrf_token':csrf_from(client.get('/').text)},
        files={'file':('synthetic.xlsx',data,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}, follow_redirects=False)


def rewrite(data, part, old, new):
    result = BytesIO()
    with ZipFile(BytesIO(data)) as source, ZipFile(result,'w',ZIP_DEFLATED) as target:
        for name in source.namelist():
            value = source.read(name)
            target.writestr(name, value.replace(old,new) if name==part else value)
    return result.getvalue()


@pytest.mark.parametrize('raw', ['NaN','Infinity','-Infinity','1e999999','-1','0','60','1.5','2958466'])
def test_numeric_excel_date_errors(raw):
    with pytest.raises(ValueError):
        excel_date(raw)


def test_calendar_anchors_leap_days_boundaries_and_missed_notice():
    assert add_months(date(2024,1,31),1) == date(2024,2,29)
    assert calculate_next_end_date(date(2024,1,31),1,date(2024,3,1)) == date(2024,3,31)
    assert add_months(date(2024,2,29),12) == date(2025,2,28)
    assert calculate_notice_deadline(date(2024,5,31),3) == date(2024,2,29)
    assert excel_date('1') == '1900-01-01'
    assert excel_date('59') == '1900-02-28'
    assert excel_date('61') == '1900-03-01'
    assert excel_date('2958465') == '9999-12-31'
    for anchor, months in ((date.min,-1),(date.max,1)):
        with pytest.raises(ValueError):
            add_months(anchor,months)
    row = SimpleNamespace(end_date=date(2024,1,31), automatic_renewal=True,
        renewal_period_months=12, notice_period_months=3, status='active')
    result = contract_dates(row,date(2024,1,1))
    assert result['notice_missed'] and result['next_end_date']==date(2024,1,31)
    assert result['legal_cancellation_verified'] is False
    row.status='terminated'
    assert contract_dates(row,date(2026,1,1))['next_end_date']==row.end_date
    assert contract_dates(row)['notice_deadline'] is None
    row.status='active';row.end_date=date.max;row.renewal_period_months=0
    assert contract_dates(row)['date_error']


def test_xlsx_unicode_strings_formulas_headers_and_references():
    data = workbook(designation='Ärztlicher Vertrag =1+1')
    assert read_xlsx(data)[0][1]['designation']=='Ärztlicher Vertrag =1+1'
    data = rewrite(data,'xl/worksheets/sheet1.xml',b'>designation<',b'>designation<')
    # A cached result must not conceal a formula.
    for altered in (
        rewrite(data,'xl/worksheets/sheet1.xml',b'<ns0:is>',b'<ns0:f>1+1</ns0:f><ns0:is>'),
        rewrite(data,'xl/worksheets/sheet1.xml',b'r="A2"',b'r="A3"'),
        rewrite(data,'xl/worksheets/sheet1.xml',b'r="A2"',b'r="XFE2"'),
        rewrite(data,'xl/worksheets/sheet1.xml',b'>contract_type<',b'>designation<'),
        rewrite(data,'xl/workbook.xml',b'<sheets>',b'<workbookPr date1904="1"/><sheets>'),
    ):
        assert altered!=data
        with pytest.raises(ValueError):
            read_xlsx(altered)
    # Actual shared strings, including invalid negative indices.
    shared = rewrite(data,'xl/worksheets/sheet1.xml',b't="inlineStr"><ns0:is><ns0:t>designation</ns0:t></ns0:is>',b't="s"><ns0:v>0</ns0:v>')
    output=BytesIO()
    with ZipFile(BytesIO(shared)) as src, ZipFile(output,'w',ZIP_DEFLATED) as dst:
        for name in src.namelist(): dst.writestr(name,src.read(name))
        dst.writestr('xl/sharedStrings.xml',b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>designation</t></si></sst>')
    assert read_xlsx(output.getvalue())[0][1]['designation'].startswith('Ärztlicher')
    with pytest.raises(ValueError):
        read_xlsx(rewrite(output.getvalue(),'xl/worksheets/sheet1.xml',b'<ns0:v>0</ns0:v>',b'<ns0:v>-1</ns0:v>'))


def test_financial_reconciliation_preserves_unknowns():
    groups = aggregate([dict(department_id=1,financial_direction=d,value_basis=b,annual_value=v)
        for d,b,v in [('expense','net','100'),('expense','gross','119'),(None,None,'12'),('income','net',None),('income','gross','0')]])
    assert sum(g['record_count'] for g in groups)==5
    assert sum(g['known_count'] for g in groups)==4
    assert sum(g['annual'] or 0 for g in groups)==Decimal('231')
    assert next(g for g in groups if g['direction']=='unknown')['annual']==12


def test_import_identity_atomicity_and_natural_duplicates(finance):
    client,app,owner=finance
    login(client,'kultur')
    assert upload(client,workbook(external_reference='SOURCE-1',value_basis='net')).status_code==303
    assert upload(client,workbook(external_reference='SOURCE-1')).status_code==422
    assert upload(client,workbook(contract_number='VR-EXISTING')).status_code==422
    assert upload(client,workbook(relevant_date='Infinity')).status_code==422
    assert upload(client,workbook(end_date='9999-12-31',automatic_renewal='1',renewal_period_months='1')).status_code==422
    for _ in range(2):
        assert upload(client,workbook()).status_code==303
    with owner.state.session_factory() as db:
        rows=db.scalars(select(Contract)).all()
        assert len(rows)==3 and rows[0].value_basis=='net'
        revisions=db.scalars(select(Revision).where(Revision.action=='created')).all()
        assert all(r.after['source']=='excel_import' and len(r.after['import_sha256'])==64 for r in revisions)
    # An invalid second row rolls back the entire workbook, even if first is valid.
    headers=['designation','contract_type','relevant_date','contact_person','external_reference']
    invalid=make_xlsx(headers,[['First','Miete','2026-01-01','Dienststelle','ATOMIC'],['Second','Miete','NaN','Dienststelle','OTHER']])
    assert upload(client,invalid).status_code==422
    with owner.state.session_factory() as db:
        assert len(db.scalars(select(Contract)).all())==3


def test_history_population_department_transfer_and_archive(finance):
    client,app,owner=finance
    login(client,'admin');record=create_contract(client)
    # Synthetic ledger fixtures appended as past recorded observations; no existing
    # audit row is rewritten. They contain no real municipal data.
    with owner.state.session_factory() as db:
        base=dict(department_id=1,financial_direction='expense',value_basis='net',annual_value='100',archived_at=None)
        db.add(Revision(contract_id=record,actor_id=1,action='created',before=None,after=base,created_at=datetime(2023,1,1)))
        moved={**base,'department_id':2,'annual_value':'250','financial_direction':'income','value_basis':'gross'}
        db.add(Revision(contract_id=record,actor_id=1,action='updated',before=base,after=moved,created_at=datetime(2024,2,1)))
        db.add(Revision(contract_id=record,actor_id=1,action='archived',before=moved,after={**moved,'archived_at':'2025-01-01'},created_at=datetime(2025,1,1)))
        db.commit()
    # Today's physical population is transferred and archived, so filtering by
    # currently visible/unarchived contracts would erase the past observations.
    edit=contract_payload(department_id='2')
    edit.update(csrf_token=csrf_from(client.get(f'/contracts/{record}/edit').text), version='1',
        annual_value='250',financial_direction='income',value_basis='gross')
    assert client.post(f'/contracts/{record}/edit',data=edit,follow_redirects=False).status_code==303
    assert client.post(f'/contracts/{record}/archive',data={'csrf_token':csrf_from(client.get(f'/contracts/{record}').text),'version':'2'},follow_redirects=False).status_code==303
    create_contract(client,designation='Current unknown financial metadata')
    # Use actual HTTP report contexts, including a restricted PostgreSQL LOGIN.
    client.post('/logout',data={'csrf_token':csrf_from(client.get('/').text)})
    login(client,'kultur')
    response=client.get('/reports');assert response.status_code==200
    assert client.get(f'/contracts/{record}').status_code==404
    years=response.context['trend']
    old=next(t for t in years if t['year']==2023)
    assert old['expenses']==100 and old['groups'][0]['basis']=='net'
    assert next(t for t in years if t['year']==2024)['groups']==[]
    assert next(t for t in years if t['year']==2025)['groups']==[]
    assert client.get('/reports').context['unknown_basis_count']==1
    # Unknown direction remains separate in current inventory.
    assert client.get('/reports').context['annual_expenses']==0
    client.post('/logout',data={'csrf_token':csrf_from(client.get('/').text)})
    login(client,'bau');years=client.get('/reports').context['trend']
    assert next(t for t in years if t['year']==2023)['groups']==[]
    assert next(t for t in years if t['year']==2024)['income']==250
    assert next(t for t in years if t['year']==2025)['groups']==[]


def test_scoped_external_identity_database_constraint(finance):
    client,app,owner=finance
    login(client,'admin');a=create_contract(client);b=create_contract(client,'2')
    with owner.state.session_factory() as db:
        db.get(Contract,a).external_reference='EXACT';db.get(Contract,b).external_reference='EXACT';db.commit()
    duplicate=create_contract(client)
    with owner.state.session_factory() as db:
        db.get(Contract,duplicate).external_reference='EXACT'
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
        assert db.get(Contract,duplicate).external_reference is None


def test_concurrent_import_identity_and_unknown_header_rejection(finance):
    from fastapi.testclient import TestClient
    from threading import Barrier
    client,app,owner=finance
    clients=[TestClient(app),TestClient(app)]
    try:
        for session in clients: assert login(session,'kultur').status_code==303
        gate=Barrier(2)
        def run(session):
            gate.wait(timeout=15)
            return upload(session,workbook(external_reference='CONCURRENT')).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(run,clients))==[303,422]
        with owner.state.session_factory() as db:
            assert len(db.scalars(select(Contract)).all())==1
        assert upload(clients[0],workbook(id='1')).status_code==422
    finally:
        for session in clients: session.close()


def test_date_validation_display_and_api_consistency(finance):
    from tests.test_phase6 import token
    client,app,owner=finance
    login(client,'admin')
    payload=contract_payload()
    payload.update(csrf_token=csrf_from(client.get('/contracts/new').text),end_date='2026-12-31',
        automatic_renewal='1',renewal_period_months='12',notice_period_months='3',status='terminated')
    created=client.post('/contracts/new',data=payload,follow_redirects=False)
    assert created.status_code==303
    cid=int(created.headers['location'].split('/contracts/')[1].split('?')[0])
    detail=client.get(f'/contracts/{cid}')
    assert detail.context['next_end_date']==date(2026,12,31) and detail.context['notice_deadline'] is None
    headers,_=token(finance,scopes='metadata,finance')
    api=client.get(f'/api/v2/contracts/{cid}',headers=headers)
    assert api.status_code==200
    assert api.json()['data']['calendar_estimate']['next_end_date']=='2026-12-31'
    assert api.json()['data']['calendar_estimate']['notice_deadline'] is None
    assert api.json()['data']['finance']['value_basis']=='unknown'
    # Lower boundary and renewal overflow are rejected before writing.
    for changes in (dict(relevant_date='0001-01-01',end_date='0001-01-01',notice_period_months='1'),
                    dict(end_date='9999-12-31',automatic_renewal='1',renewal_period_months='12')):
        bad={**contract_payload(),**changes,'csrf_token':csrf_from(client.get('/contracts/new').text)}
        assert client.post('/contracts/new',data=bad).status_code==422


@pytest.mark.postgresql
def test_postgresql_history_function_is_narrow_and_reauthenticates(finance,request):
    if request.config.getoption('--database')!='postgresql':
        pytest.skip('Actual restricted PostgreSQL history authorization required')
    from app.security import COOKIE_NAME
    client,app,owner=finance
    login(client,'kultur')
    # A runtime connection cannot choose an arbitrary principal to widen history.
    with app.state.engine.connect() as c:
        with pytest.raises(DBAPIError):
            c.execute(text("SELECT * FROM ohvr_security.financial_history(timestamp '2024-12-31')")).all()
        c.rollback()
        assert c.scalar(text("SELECT has_function_privilege(current_user,'ohvr_security.financial_history(timestamp)','EXECUTE')"))
    with app.state.integration_engine.connect() as c:
        assert not c.scalar(text("SELECT has_function_privilege(current_user,'ohvr_security.financial_history(timestamp)','EXECUTE')"))


def test_import_refreshes_membership_before_assigning_ownership(finance,monkeypatch):
    import app.main as main
    client,app,owner=finance
    login(client,'kultur')
    original=main.read_xlsx
    def membership_changed_during_parse(data):
        rows=original(data)
        with owner.state.session_factory() as db:
            db.scalar(select(User).where(User.username=='kultur')).department_id=2
            db.commit()
        return rows
    monkeypatch.setattr(main,'read_xlsx',membership_changed_during_parse)
    assert upload(client,workbook(external_reference='CURRENT-MEMBERSHIP')).status_code==303
    with owner.state.session_factory() as db:
        assert db.scalar(select(Contract)).department_id==2
