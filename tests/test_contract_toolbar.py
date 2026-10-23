"""Toolbar links must operate on the real scoped result set and XLSX export."""
from datetime import date
from io import BytesIO
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from app.models import Contract
from tests.support import login
from tests.test_frontend_redesign import Markup

def params(url):
    return parse_qs(urlsplit(url).query)

def seed(app):
    with app.state.session_factory() as db:
        for index in range(32):
            db.add(Contract(contract_number=f'TOOL-{index:03}',designation='Synthetic toolbar contract',
                contract_type='Miete',relevant_date=date(2026,1,1),department_id=1 if index<30 else 2,
                contact_person='Dienststelle',deputy_contact_person='Vertretung',status='draft',
                created_by_id=1,updated_by_id=1))
        db.add(Contract(contract_number='OTHER-001',designation='Another test record',contract_type='Dienstleistung',
            relevant_date=date(2026,1,1),department_id=1,contact_person='Dienststelle',
            created_by_id=1,updated_by_id=1))
        db.commit()

@pytest.mark.parametrize('role,total', [('admin',33),('kultur',31),('pruefer',33)])
def test_toolbar_search_remove_reset_pagination_export(environment,role,total):
    client,app=environment;seed(app);login(client,role)
    page=client.get('/')
    assert page.context['total_count']==total
    assert page.context['toolbar']['chips']==[]
    assert 'id="advanced-filter-disclosure" open' not in page.text
    assert page.text.count('id="q"')==1
    assert ('href="/contracts/new"' in page.text)==(role!='pruefer')
    assert page.text.index('class="panel table-panel"') < page.text.index('class="pagination"')
    if role!='pruefer':assert page.text.index('class="pagination"') < page.text.index('excel-import-panel')
    Markup(page.text).labels_present()
    query=dict(q='Synthetic',status='draft',department='1',contract_type='Miete',
               contact_person='Dienststelle',deputy_contact_person='Vertretung',tax_review_status='not_checked',
               page_size='25',page='2')
    page=client.get('/',params=query);ctx=page.context;toolbar=ctx['toolbar']
    assert ctx['total_count']==30 and len(ctx['contracts'])==5
    assert len(toolbar['chips'])==(6 if role=='kultur' else 7)
    assert all(chip['key'] != 'page_size' for chip in toolbar['chips'])
    for chip in toolbar['chips']:
        values=params(chip['remove_url'])
        assert chip['key'] not in values and 'page' not in values
        if chip['key']!='q': assert values['q']==['Synthetic']
        assert values['page_size']==['25']
        assert values['contract_type']==['Miete'] if chip['key']!='contract_type' else True
        response=client.get(chip['remove_url']);assert response.status_code==200
        assert chip['key'] not in [c['key'] for c in response.context['toolbar']['chips']]
    reset=client.get(toolbar['reset_url'])
    assert reset.context['q']=='' and reset.context['toolbar']['chips']==[]
    assert reset.context['total_count']==total
    cleared=client.get(toolbar['clear_search_url'])
    assert cleared.context['q']=='' and len(cleared.context['toolbar']['chips'])==len(toolbar['chips'])-1
    assert cleared.context['total_count']==30
    previous=client.get(ctx['previous_page_url'])
    assert previous.context['total_count']==30 and len(previous.context['contracts'])==25
    ids=[c.id for c in previous.context['contracts']]+[c.id for c in ctx['contracts']]
    assert len(set(ids))==30
    export=client.get(toolbar['export_url'])
    assert export.status_code==200
    with ZipFile(BytesIO(export.content)) as book:
        sheet=ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
        assert len(sheet.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'))==31
    if role=='kultur':
        private=client.get('/?department=2&q=TOOL-031')
        assert private.context['total_count']==0
        assert not any(c['key']=='department' for c in private.context['toolbar']['chips'])
        assert client.get('/contracts/32').status_code==404

def test_toolbar_focus_nondefault_page_size_and_escaped_queries(environment):
    client,app=environment;seed(app);login(client,'admin')
    response=client.get('/',params={'focus':'review','q':'<script>& + ä','status':'draft','page_size':1})
    Markup(response.text).labels_present()
    assert '<option value="1" selected>1</option>' in response.text
    chips=response.context['toolbar']['chips']
    assert {c['key'] for c in chips}=={'q','focus','status'}
    assert '<script>&' not in response.text
    assert params(next(c for c in chips if c['key']=='status')['remove_url'])['q']==['<script>& + ä']
    response=client.get('/?focus=active&status=archived')
    assert [c['key'] for c in response.context['toolbar']['chips']]==['status']


def test_compact_overview_search_chip_and_scoped_summary(environment):
    client,app=environment;seed(app);login(client,'kultur')
    response=client.get('/')
    assert 'class="contract-summary"' in response.text
    assert 'class="dashboard-cards"' not in response.text
    assert 'contract-toolbar-main' not in response.text
    assert 'Keine überfälligen oder anstehenden Vertragsfristen.' in response.text
    assert response.context['focus_counts']==client.get('/dashboard').context['focus_counts']
    # Search belongs to the closed disclosure; export belongs to the table header.
    start=response.text.index('id="advanced-filter-disclosure"')
    end=response.text.index('</details>',start)
    assert start < response.text.index('id="q"') < end
    assert response.text.index('contract-list-heading') < response.text.index('Alle Treffer exportieren')
    search=client.get('/?q=Synthetic&page_size=25')
    assert [c['key'] for c in search.context['toolbar']['chips']]==['q']
    assert 'Suche &amp; Filter (1)' in search.text
    cleared=client.get(search.context['toolbar']['chips'][0]['remove_url'])
    assert cleared.context['total_count']==31 and cleared.context['page_size']==25
