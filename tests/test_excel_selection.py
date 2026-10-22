"""Real scoped XLSX responses, hostile selections and unchanged atomic import."""
from io import BytesIO
from urllib.parse import urlencode
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from sqlalchemy import select
from app.excel import EXPORT_COLUMNS, read_xlsx
from app.listing import selected_export_ids, EXPORT_MAX_ROWS
from app.models import Contract, IdentityAudit, User, Department
from tests.support import login, csrf_from
from tests.test_contract_toolbar import seed
from tests.test_frontend_redesign import Markup
from tests.test_phase7 import workbook, upload, rewrite

URL='/contracts/export-selected.xlsx'

def export(client, ids, csrf=None):
    return client.post(URL, data={'csrf_token':csrf if csrf is not None else csrf_from(client.get('/').text),
                                 'contract_ids':ids}, follow_redirects=False)

def numbers(response):
    assert response.status_code==200
    assert 'attachment;' in response.headers['content-disposition']
    assert set(part.strip() for part in response.headers['cache-control'].split(','))=={'no-store'}
    return {row['contract_number'] for _,row in read_xlsx(response.content)}

@pytest.mark.parametrize('role,ids', [('admin','1,32'),('kultur','1,2'),('bau','31,32'),('pruefer','1,32')])
def test_single_multiple_and_scoped_page_selection(environment,role,ids):
    client,app=environment;seed(app);login(client,role)
    page=client.get('/?page_size=25');Markup(page.text).labels_present()
    assert page.context['can_export']
    assert 'id="export-selection" disabled' in page.text
    assert 'id="select-page"' in page.text and 'Alle Treffer exportieren' in page.text
    one=int(ids.split(',')[0])
    assert numbers(export(client,str(one)))=={f'TOOL-{one-1:03}'}
    assert numbers(export(client,ids))=={f'TOOL-{int(i)-1:03}' for i in ids.split(',')}
    current=page.context['contracts']
    assert numbers(export(client,','.join(str(c.id) for c in current)))=={c.contract_number for c in current}
    # Complete filtered export remains independent of selection and page size.
    expected=2 if role=='bau' else 30 if role=='kultur' else 32
    assert len(numbers(client.get('/contracts/export.xlsx?q=Synthetic')))==expected
    with app.state.session_factory() as db:
        events=db.scalars(select(IdentityAudit).where(IdentityAudit.action=='contract_selection_export_prepared')).all()
        assert [e.details['record_count'] for e in events]==[1,2,len(current)]
        assert all(set(e.details)=={'record_count','contract_ids'} for e in events)

@pytest.mark.parametrize('raw,status', [('',422),('1,1',422),('01',422),('0',422),('-1',422),
    ('1,',422),('1,,2',422),(' 1',422),('1.0',422),('١',422),('2147483648',422),('1 OR 1=1',422),
    ('1,32',404),('1,999999',404)])
def test_reject_entire_invalid_or_inaccessible_selection(environment,raw,status):
    client,app=environment;seed(app);login(client,'kultur')
    response=export(client,raw)
    assert response.status_code==status and 'content-disposition' not in response.headers
    assert 'TOOL-031' not in response.text and 'Synthetic toolbar contract' not in response.text
    with app.state.session_factory() as db:
        assert not db.scalar(select(IdentityAudit.id).where(IdentityAudit.action=='contract_selection_export_prepared'))

def test_csrf_duplicate_fields_guest_and_revoked_membership(environment):
    client,app=environment;seed(app)
    assert client.post(URL,data={'contract_ids':'1'},follow_redirects=False).status_code==303
    login(client,'kultur');csrf=csrf_from(client.get('/').text)
    assert export(client,'1',csrf='bad').status_code==403
    response=client.post(URL,content=urlencode([('csrf_token',csrf),('contract_ids','1'),('contract_ids','2')]),
                         headers={'content-type':'application/x-www-form-urlencoded'})
    assert response.status_code==400 and 'content-disposition' not in response.headers
    with app.state.session_factory() as db:
        db.get(User,2).department_id=2;db.commit()
    assert export(client,'1',csrf=csrf).status_code in (303,404)
    with app.state.session_factory() as db:
        db.get(Department,2).is_active=False;db.commit()
    assert export(client,'31',csrf=csrf).status_code==303

def test_selection_bounds_and_same_export_budget(environment,monkeypatch):
    import app.main as main
    assert EXPORT_MAX_ROWS==5000
    assert len(selected_export_ids(','.join(str(i) for i in range(1,5001))))==5000
    with pytest.raises(OverflowError):selected_export_ids(','.join(str(i) for i in range(1,5002)))
    client,app=environment;seed(app);login(client,'admin')
    assert export(client,','.join(str(i) for i in range(1,5002))).status_code==413
    monkeypatch.setattr(main,'EXPORT_MAX_ROWS',1)
    assert export(client,'1,2').status_code==413
    assert client.get('/contracts/export.xlsx').status_code==413
    assert export(client,'1').status_code==200

def test_selection_preserves_workbook_schema_and_literal_formula_text(environment):
    client,app=environment;seed(app);login(client,'admin')
    with app.state.session_factory() as db:
        c=db.get(Contract,1);c.designation='=HYPERLINK("https://example.invalid","test")'
        c.contract_partner='+1+1';c.contact_person='@SUM(1)';c.deputy_contact_person='-1+1';db.commit()
    response=export(client,'1')
    rows=read_xlsx(response.content);assert len(rows)==1
    assert rows[0][1]['designation'].startswith('=HYPERLINK')
    with ZipFile(BytesIO(response.content)) as book:
        assert set(book.namelist())=={'[Content_Types].xml','_rels/.rels','xl/workbook.xml',
                                     'xl/_rels/workbook.xml.rels','xl/worksheets/sheet1.xml'}
        sheet=ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
        ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        assert sheet.findall('.//m:f',ns)==[]
        headings=[c.find('m:is/m:t',ns).text for c in sheet.find('m:sheetData/m:row',ns)]
        assert headings==[label for _,label in EXPORT_COLUMNS]

def test_import_ui_atomic_errors_and_confirmed_success(environment):
    client,app=environment;login(client,'kultur')
    page=client.get('/');Markup(page.text).labels_present()
    assert page.text.index('class="pagination"') < page.text.index('id="excel-import-title"')
    assert '<details class="excel-import-notes">' in page.text
    assert 'Verträge aus Excel importieren' in page.text
    assert upload(client,workbook(external_reference='NEW')).status_code==303
    response=upload(client,workbook(external_reference='NEW'))
    assert response.status_code==422 and 'Import nicht durchgeführt' in response.text
    assert 'externe Referenz' in response.text
    with app.state.session_factory() as db:
        assert len(db.scalars(select(Contract)).all())==1
    client.cookies.clear();login(client,'pruefer')
    assert 'id="excel-import-title"' not in client.get('/').text
    assert upload(client,workbook()).status_code==403


def test_full_hundred_row_page_uses_bounded_single_id_field(environment):
    from datetime import date
    client,app=environment;login(client,'admin')
    with app.state.session_factory() as db:
        db.add_all([Contract(contract_number=f'PAGE-{i}',designation='Synthetic page export',contract_type='Miete',
            relevant_date=date(2026,1,1),department_id=1,contact_person='Dienststelle',created_by_id=1,updated_by_id=1)
            for i in range(100)])
        db.commit()
    page=client.get('/?page_size=100')
    ids=','.join(str(c.id) for c in page.context['contracts'])
    assert len(numbers(export(client,ids)))==100
    assert app.state.config.form_max_fields==40  # No global ingress-limit relaxation.


def test_import_formula_error_is_localized_and_atomic(environment):
    client,app=environment;login(client,'kultur')
    data=rewrite(workbook(),'xl/worksheets/sheet1.xml',b'<ns0:is>',b'<ns0:f>1+1</ns0:f><ns0:is>')
    response=upload(client,data)
    assert response.status_code==422
    assert 'Formeln sind nicht zulässig' in response.text and 'Zeile 1' in response.text
    with app.state.session_factory() as db:
        assert not db.scalar(select(Contract.id))
