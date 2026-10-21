"""Use the same configured engine as the application."""
from alembic import context
from dataclasses import replace
from app.config import get_settings
from app.db import Base, make_engine
from app import models  # noqa: F401, registers models

config = context.config
target_metadata = Base.metadata


def run_migrations_offline():
    # Offline SQL requires a database URL and no live credentials in output.
    raise RuntimeError("Offline migration is intentionally not supported")


def run_migrations_online():
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        run_on_connection(supplied_connection)
        return
    settings = get_settings()
    if settings.enforce_database_security:
        if not settings.migration_database_url:
            raise RuntimeError('Explicit MIGRATION_DATABASE_URL required; web credentials cannot migrate')
        settings = replace(settings, database_url=settings.migration_database_url)
    engine = make_engine(settings)
    try:
        with engine.connect() as connection:
            run_on_connection(connection)
    finally:
        engine.dispose()


def run_on_connection(connection):
    if connection.dialect.name == 'sqlite':
        # SQLite table rebuilds require FK checks off outside a transaction.
        # Own an explicit transaction so a failed rebuild rolls back DDL too.
        if connection.in_transaction():
            raise RuntimeError('Finish the caller transaction before SQLite migration')
        connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
        connection.commit()
        try:
            connection.exec_driver_sql('BEGIN')
            context.configure(connection=connection, target_metadata=target_metadata,
                              compare_type=True, render_as_batch=True)
            context.run_migrations()
            if connection.exec_driver_sql('PRAGMA foreign_key_check').fetchone():
                raise RuntimeError('SQLite migration FK validation failed; rolled back')
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
            connection.commit()
        return
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True, render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
