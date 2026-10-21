"""Query optimizations retain scoped filters and unchanged PostgreSQL read rules."""
import pytest
from sqlalchemy import event, select, text
from app.financial import aggregate,current_groups
from app.logic import snapshot
from app.models import Contract,User

from tests.support import environment_context, login, create_contract
from tests.runtime_support import runtime_environment
from tests.test_phase3 import runtime_session
from app.security import COOKIE_NAME


def test_dashboard_does_not_materialize_undated_population(request):
    with environment_context(request.config.getoption('--database')) as (client,app):
        assert login(client,'admin').status_code==303
        create_contract(client)
        statements=[]
        def capture(conn,cursor,statement,parameters,context,many):
            if statement.lstrip().lower().startswith('select contracts.id'):
                statements.append(statement.lower())
        event.listen(app.state.engine,'before_cursor_execute',capture)
        try:
            assert client.get('/').status_code==200
        finally:
            event.remove(app.state.engine,'before_cursor_execute',capture)
        assert statements
        assert all('limit' in query or 'contracts.end_date is not null' in query for query in statements)


def test_database_finance_groups_match_existing_known_unknown_rules(request):
    with environment_context(request.config.getoption('--database')) as (client,app):
        assert login(client,'admin').status_code==303
        first=create_contract(client)
        second=create_contract(client,department_id='2')
        with app.state.session_factory() as db:
            db.get(Contract,first).annual_value=0
            db.get(Contract,first).financial_direction='expense'
            db.get(Contract,first).value_basis='net'
            db.get(Contract,second).annual_value=None
            db.commit()
            population=db.scalars(select(Contract)).all()
            admin=db.scalar(select(User).where(User.username=='admin'))
            scoped=db.scalar(select(User).where(User.username=='kultur'))
            assert current_groups(db,admin)==aggregate(snapshot(c) for c in population)
            assert current_groups(db,scoped)==aggregate(snapshot(c) for c in population if c.department_id==scoped.department_id)


@pytest.mark.postgresql
def test_read_department_initplan_is_equivalent_for_live_principals(request):
    if request.config.getoption('--database')!='postgresql':
        pytest.skip('Actual restricted PostgreSQL logins required')
    with runtime_environment() as runtime:
        for name in ('admin','kultur','bau','pruefer'):
            runtime.client.cookies.clear()
            assert login(runtime.client,name).status_code==303
            with runtime_session(runtime,cookie=runtime.client.cookies.get(COOKIE_NAME)) as db:
                expected=db.scalars(text('SELECT id FROM departments WHERE ohvr_security.read_department(id) ORDER BY id')).all()
                actual=db.scalar(text('SELECT ohvr_security.read_departments()'))
                assert sorted(actual)==expected
                plan=db.scalar(text('EXPLAIN (VERBOSE, FORMAT JSON) SELECT id FROM contracts'))
                assert 'InitPlan' in str(plan) and 'read_departments' in str(plan)
        with runtime.app.state.engine.connect() as connection:
            assert connection.scalar(text("""SELECT NOT EXISTS (
                SELECT 1 FROM pg_proc p,
                LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
                WHERE p.oid='ohvr_security.read_departments()'::regprocedure
                AND a.grantee=0 AND a.privilege_type='EXECUTE')""")) is True
