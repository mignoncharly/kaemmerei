"""Add financial classification and payment information to contracts."""
from alembic import op
import sqlalchemy as sa

revision = "0010_contract_financial_details"
down_revision = "0009_contract_tasks"
branch_labels = None
depends_on = None


def upgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("contracts")}
    additions = (
        sa.Column("contract_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("financial_direction", sa.String(length=12), nullable=True),
        sa.Column("payment_interval", sa.String(length=16), nullable=True),
        sa.Column("budget_assignment", sa.String(length=120), nullable=False, server_default=""),
    )
    for column in additions:
        if column.name not in existing:
            op.add_column("contracts", column)


def downgrade():
    op.drop_column("contracts", "budget_assignment")
    op.drop_column("contracts", "payment_interval")
    op.drop_column("contracts", "financial_direction")
    op.drop_column("contracts", "contract_value")
