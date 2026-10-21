"""Explicit real PostgreSQL lifecycle; never falls back to SQLite."""
import os
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.db import make_engine
from app.config import Settings
from app.migrations import migration_head, upgrade_connection
from tests.support import disposable_database, scratch_directory

pytestmark = pytest.mark.postgresql


def test_postgresql_clean_migration_identity_and_cleanup(request):
    if request.config.getoption('--database') != 'postgresql':
        pytest.skip('Run explicitly with --database postgresql; SQLite is not PostgreSQL evidence')
    admin = make_url(os.environ['TEST_POSTGRES_ADMIN_URL']).set(drivername='postgresql')
    with scratch_directory('ohvr-pg-lifecycle-') as directory:
        with disposable_database('postgresql', Path(directory)) as target:
            name = make_url(target).database
            assert name.startswith('ohvr_test_') and name != 'postgres'
            engine = make_engine(Settings(database_url=target))
            try:
                with engine.connect() as connection:
                    assert connection.dialect.name == 'postgresql'
                    assert connection.scalar(text('select current_user')) == 'ohvr_verify'
                    assert connection.scalar(text('select current_database()')) == name
                    assert connection.scalar(text("select count(*) from information_schema.tables where table_schema='public'")) == 0
                    upgrade_connection(connection)
                    assert connection.scalar(text('select version_num from alembic_version')) == migration_head()
                    upgrade_connection(connection)
            finally:
                engine.dispose()
        with psycopg.connect(admin.render_as_string(hide_password=False), connect_timeout=5) as control:
            assert control.execute('select 1 from pg_database where datname=%s', (name,)).fetchone() is None
