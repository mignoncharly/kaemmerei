"""Forward query optimization must preserve the security-definer contract."""
from pathlib import Path
import pytest
from sqlalchemy import text
from app.config import Settings
from app.db import make_engine
from app.migrations import upgrade_connection
from tests.support import disposable_database, scratch_directory


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
