"""Database connections. Schema changes are managed with Alembic."""
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import Settings


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings) -> Engine:
    kwargs = {"pool_pre_ping": True, "hide_parameters": True}
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
            connection.create_function('ohvr_actor', 0, lambda: connection_record.info.get('actor_id'))
            connection.create_function('ohvr_correlation', 0, lambda: connection_record.info.get('correlation_id') or str(uuid4()))
    return engine


def make_session_factory(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, 'after_begin')
def transaction_identity(session, transaction, connection):
    if transaction.nested:
        return
    context = session.info.get('request_context', {})
    correlation = context.get('correlation_id') or str(uuid4())
    if connection.dialect.name == 'postgresql':
        if session.info.get('enforce_rls'):
            try:
                connection.execute(text('SELECT ohvr_security.prepare_context(:session,:token,:correlation)'),
                                   {'session':context.get('session_hash',''), 'token':context.get('token_hash',''), 'correlation':correlation})
            except Exception:
                raise RuntimeError('Database request identity initialization failed') from None
    else:
        connection.info['actor_id'] = None
        connection.info['correlation_id'] = correlation


@event.listens_for(Session, 'before_flush')
def audit_correlation(session, flush_context, instances):
    from app.models import IdentityAudit, Revision
    for item in session.new:
        if isinstance(item, IdentityAudit):
            item.correlation_id = session.info.get('request_context', {}).get('correlation_id') or str(uuid4())
        if isinstance(item,Revision) and session.info.get('submission_id'):
            item.after={**item.after,'request_id':session.info['submission_id']}
