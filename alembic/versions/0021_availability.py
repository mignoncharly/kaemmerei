"""Shared bounded API admission and authentication cleanup indexes."""
from pathlib import Path
from alembic import op

revision = '0021_availability'
down_revision = '0020_financial_reports'
branch_labels = depends_on = None


def upgrade():
    op.create_index('ix_login_attempts_key_created', 'login_attempts', ['key_hash','created_at'])
    op.create_index('ix_login_attempts_created_at', 'login_attempts', ['created_at'])
    if op.get_bind().dialect.name == 'postgresql':
        op.get_bind().exec_driver_sql((Path(__file__).resolve().parents[1]/'sql'/'0021_availability.sql').read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('Forward only: preserve shared admission controls')
