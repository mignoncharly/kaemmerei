"""Bounded multi-cutoff historical inventory; same principal/population rules."""
from pathlib import Path
from alembic import op

revision='0025_history_series'
down_revision='0024_history_materialization'
branch_labels=depends_on=None


def upgrade():
    connection=op.get_bind()
    if connection.dialect.name=='postgresql':
        connection.exec_driver_sql((Path(__file__).resolve().parents[1]/'sql'/'0025_history_series.sql').read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('Forward only: preserve verified historical series')
