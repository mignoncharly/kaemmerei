"""Explicit value basis, scoped external identity and minimal historical aggregates."""
from pathlib import Path
from alembic import op

revision = '0020_financial_reports'
down_revision = '0019_integration_sync'
branch_labels = depends_on = None


def upgrade():
    c = op.get_bind()
    # Additive DDL preserves all existing SQLite audit/archive/sync triggers.
    c.exec_driver_sql("ALTER TABLE contracts ADD COLUMN value_basis VARCHAR(12) NOT NULL DEFAULT 'unknown' CONSTRAINT contract_value_basis CHECK (value_basis IN ('net','gross','unknown'))")
    c.exec_driver_sql('ALTER TABLE contracts ADD COLUMN external_reference VARCHAR(120)')
    op.create_index('ux_contracts_department_external', 'contracts', ['department_id', 'external_reference'], unique=True)
    if c.dialect.name == 'postgresql':
        c.exec_driver_sql((Path(__file__).resolve().parents[1] / 'sql' / '0020_reports.sql').read_text(encoding='utf-8').replace('%', '%%'))


def downgrade():
    raise RuntimeError('Forward only: preserve financial basis, references and recorded history')
