"""Add a lifecycle status to each contract.

Revision ID: 0002_contract_status
Revises: 0001_initial
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_contract_status"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("contracts", sa.Column(
        "status", sa.String(length=20), nullable=False, server_default="active"
    ))
    if op.get_bind().dialect.name == "sqlite":
        # SQLite cannot add a table-level CHECK constraint without rebuilding
        # this table, which is referenced by the revision history. Triggers
        # enforce the same allowed values without disturbing those foreign keys.
        op.execute("""
            CREATE TRIGGER ck_contract_status_insert
            BEFORE INSERT ON contracts
            WHEN NEW.status NOT IN ('draft', 'in_progress', 'active', 'terminated', 'ended')
            BEGIN SELECT RAISE(ABORT, 'invalid contract status'); END
        """)
        op.execute("""
            CREATE TRIGGER ck_contract_status_update
            BEFORE UPDATE OF status ON contracts
            WHEN NEW.status NOT IN ('draft', 'in_progress', 'active', 'terminated', 'ended')
            BEGIN SELECT RAISE(ABORT, 'invalid contract status'); END
        """)
    else:
        op.create_check_constraint(
            "valid_contract_status", "contracts",
            "status IN ('draft', 'in_progress', 'active', 'terminated', 'ended')",
        )


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER ck_contract_status_insert")
        op.execute("DROP TRIGGER ck_contract_status_update")
    else:
        op.drop_constraint("valid_contract_status", "contracts", type_="check")
    op.drop_column("contracts", "status")
