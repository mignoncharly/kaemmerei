"""Keep bounded history series linear in source size, without a join-back."""
from pathlib import Path
from alembic import op
import sqlalchemy as sa

revision='0026_history_projection'
down_revision='0025_history_series'
branch_labels=depends_on=None


def upgrade():
    connection=op.get_bind()
    if connection.dialect.name!='postgresql':return
    definition=connection.scalar(sa.text("SELECT pg_get_functiondef('ohvr_security.financial_history_series(timestamp[])'::regprocedure)"))
    marker=' RETURN QUERY '
    if not definition or definition.count(marker)!=1:
        raise RuntimeError('Unexpected series definition; explicit forward review required')
    start=definition.index(marker)
    end=definition.index('\nEND',start)
    query=(Path(__file__).resolve().parents[1]/'sql'/'0026_history_projection.sql').read_text(encoding='utf-8').strip().rstrip(';')
    # Signature, owner, ACL and every principal/input guard remain unchanged.
    connection.exec_driver_sql(definition[:start]+marker+query+';'+definition[end:])


def downgrade():
    raise RuntimeError('Forward only: retain verified bounded history series')
