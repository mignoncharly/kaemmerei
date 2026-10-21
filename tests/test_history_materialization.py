"""Forward query optimization must preserve the security-definer contract."""
from pathlib import Path
import pytest
from sqlalchemy import text
from app.config import Settings
from app.db import make_engine
from app.migrations import upgrade_connection
from tests.support import disposable_database, scratch_directory


@pytest.mark.postgresql
def test_series_matches_scalar_history_with_transfer_archive_unknowns_and_permissions(request):
    if request.config.getoption('--database')!='postgresql':
        pytest.skip('Actual restricted PostgreSQL history required')
    from datetime import date, datetime, timedelta
    from decimal import Decimal
    from unittest.mock import patch
    from sqlalchemy import event, select
    from sqlalchemy.exc import DBAPIError
    from app.financial import inventory_trend
    from app.logic import snapshot
    from app.models import Contract, Revision, User, now_utc
    from app.security import COOKIE_NAME
    from tests.runtime_support import runtime_environment
    from tests.support import login
    from tests.test_phase3 import runtime_session
    with runtime_environment() as runtime:
        with runtime.owner.state.session_factory() as db:
            actor=db.scalar(select(User.id).where(User.username=='admin'))
            for index in range(3):
                c=Contract(contract_number=f'SER-{index}',designation='Synthetic historical scope',
                    contract_type='Miete',relevant_date=date(2024,1,1),department_id=1,
                    created_by_id=actor,updated_by_id=actor)
                db.add(c);db.flush()
                db.add(Revision(contract_id=c.id,actor_id=actor,action='created',
                    after=snapshot(c),created_at=datetime(2024,1,1)))
                if index==0:
                    c.department_id=2;c.annual_value=Decimal('0.00');c.financial_direction='expense';c.value_basis='net'
                    db.add(Revision(contract_id=c.id,actor_id=actor,action='updated',
                        after=snapshot(c),created_at=datetime(2025,1,1)))
                elif index==1:
                    c.archived_at=datetime(2025,1,1)
                    db.add(Revision(contract_id=c.id,actor_id=actor,action='archived',
                        after=snapshot(c),created_at=datetime(2025,1,1)))
            db.commit()
        reference=now_utc()-timedelta(seconds=1)
        cutoffs=[min(datetime(year,12,31,23,59,59,999999),reference)
                 for year in range(reference.year-4,reference.year+1)]
        def normalized(rows):return sorted([dict(row) for row in rows],key=lambda g:(g['department_id'],g['direction'],g['basis']))
        for username in ('admin','kultur'):
            runtime.client.cookies.clear()
            assert login(runtime.client,username).status_code==303
            with runtime_session(runtime,cookie=runtime.client.cookies.get(COOKIE_NAME)) as db:
                expected=[normalized(db.execute(text('SELECT * FROM ohvr_security.financial_history(:cutoff)'),
                    {'cutoff':cutoff}).mappings()) for cutoff in cutoffs]
                queries=[]
                def capture(conn,cursor,statement,parameters,context,many):
                    if 'financial_history' in statement:queries.append(statement)
                event.listen(runtime.app.state.engine,'before_cursor_execute',capture)
                try:
                    with patch('app.financial.now_utc',return_value=reference):
                        trend,_=inventory_trend(db,None,reference.date())
                finally:event.remove(runtime.app.state.engine,'before_cursor_execute',capture)
                assert [normalized(row['groups']) for row in trend]==expected
                assert len(queries)==1
                if username=='admin':
                    zero=next(g for g in trend[-1]['groups'] if g['direction']=='expense')
                    assert zero['annual']==0 and zero['known_count']==1
                if username=='kultur':assert all(g['department_id']==1 for row in trend for g in row['groups'])
                for invalid in (None,[],[reference]*6,[reference+timedelta(days=2)],[None]):
                    with pytest.raises(DBAPIError),db.begin_nested():
                        db.execute(text('SELECT * FROM ohvr_security.financial_history_series(CAST(:cutoffs AS timestamp[]))'),{'cutoffs':invalid})
        with runtime_session(runtime,integration=True) as db:
            with pytest.raises(DBAPIError),db.begin_nested():
                db.execute(text('SELECT * FROM ohvr_security.financial_history_series(CAST(:cutoffs AS timestamp[]))'),{'cutoffs':cutoffs})


@pytest.mark.postgresql
def test_history_upgrade_preserves_owner_grants_guards_and_repeatability(request):
    if request.config.getoption('--database')!='postgresql':
        pytest.skip('Actual PostgreSQL function catalog required')
    with scratch_directory('ohvr-history-upgrade-') as directory:
        with disposable_database('postgresql',Path(directory)) as target:
            engine=make_engine(Settings(database_url=target))
            try:
                with engine.connect() as connection:
                    upgrade_connection(connection,'0023_human_mfa')
                    query=text("SELECT prosrc,proowner,proacl::text,prosecdef,proconfig,provolatile FROM pg_proc WHERE oid='ohvr_security.financial_history(timestamp)'::regprocedure")
                    before=connection.execute(query).one()
                    connection.commit()
                    upgrade_connection(connection)
                    after=connection.execute(query).one()
                    assert after[1:]==before[1:]
                    assert after[0].replace('WITH latest AS MATERIALIZED (','WITH latest AS (')==before[0]
                    connection.commit()
                    upgrade_connection(connection)
                    assert connection.execute(query).one()==after
            finally:
                engine.dispose()
