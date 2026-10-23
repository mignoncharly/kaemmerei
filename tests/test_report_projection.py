"""Full scoped totals survive bounded, navigable reminder projections."""
from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.models import Contract,ContractTask,User
from tests.support import login
from tests.test_phase8 import frontend


@pytest.mark.parametrize('section,offset',[('overdue',-1),('upcoming',1)])
def test_report_pagination_retains_population_finance_tasks_and_scope(frontend,section,offset):
    client,_,owner=frontend
    today=date.today();due=today+timedelta(days=offset)
    with owner.state.session_factory() as db:
        actor=db.scalar(select(User.id).where(User.username=='admin'))
        records=[]
        for department in (1,2):
            for index in range(125):
                records.append(Contract(contract_number=f'PAGE-{department}-{index}',
                    designation=('OWN' if department==1 else 'FOREIGN')+f' {index:03d}',
                    contract_type='Miete',relevant_date=today-timedelta(days=365),end_date=due,
                    department_id=department,created_by_id=actor,updated_by_id=actor,
                    status='in_progress',annual_value=Decimal('1.00'),financial_direction='expense',value_basis='net'))
        for index,status in enumerate(('draft','ended')):
            records.append(Contract(contract_number=f'PAGE-EXTRA-{index}',designation='OWN manual task parent',
                contract_type='Miete',relevant_date=today-timedelta(days=365),end_date=due,
                department_id=1,created_by_id=actor,updated_by_id=actor,status=status,
                annual_value=Decimal('0.00') if status=='draft' else None,
                financial_direction='expense',value_basis='net'))
        db.add_all(records);db.flush()
        db.add_all(ContractTask(contract_id=c.id,title='Manual synthetic due date',kind='review',
            due_date=due,created_by_id=actor) for c in records)
        db.commit()
    assert login(client,'kultur').status_code==303
    dashboard=client.get('/')
    assert dashboard.status_code==200
    assert dashboard.context[section+'_reminder_total']==125
    assert len(dashboard.context[section+'_reminders'])==10
    assert 'FOREIGN' not in dashboard.text and 'Alle anzeigen' in dashboard.text
    if section=='upcoming':
        assert client.get('/?focus=expiring').context['total_count']==125
    seen=set()
    for page,expected_count in ((1,100),(2,100),(3,52)):
        response=client.get(f'/reports?{section}_page={page}')
        assert response.status_code==200
        data=response.context
        assert data['contract_count']==127 and data['annual_expenses']==125
        assert data['open_task_count']==127 and data['missing_annual_count']==1
        assert data[section+'_total']==252 and data[section+'_pages']==3
        items=data[section+'_items']
        assert len(items)==expected_count
        assert all(item['contract'].department_id==1 for item in items)
        keys={(item['kind'],item['contract'].id,item['task'].id if 'task' in item else 0) for item in items}
        assert seen.isdisjoint(keys);seen.update(keys)
        assert 'FOREIGN' not in response.text
        assert f'Seite {page} von 3' in response.text
    assert len(seen)==252
    assert client.get(f'/reports?{section}_page=10000').context[section+'_page']==3
    assert client.get(f'/reports?{section}_page=0').status_code==422
