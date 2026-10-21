"""Database connections. Schema changes are managed with Alembic."""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import Settings


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings) -> Engine:
    kwargs = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite:///"):
        name = settings.database_url.removeprefix("sqlite:///")
        if name != ":memory:":
            Path(name).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
    engine = create_engine(settings.database_url, **kwargs)
    if settings.database_url.startswith("sqlite:///"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, connection_record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def make_session_factory(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
