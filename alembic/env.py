"""Use the same configured engine as the application."""
from alembic import context
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
    engine = make_engine(get_settings())
    try:
        with engine.connect() as connection:
            run_on_connection(connection)
    finally:
        engine.dispose()


def run_on_connection(connection):
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True, render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
