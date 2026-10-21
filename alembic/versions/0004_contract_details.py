"""Add counterparty, contract end, notice period and yearly value fields."""
from alembic import op
import sqlalchemy as sa

revision = "0004_contract_details"
down_revision = "0003_contract_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("contracts", sa.Column("contract_partner", sa.String(length=200), nullable=False, server_default=""))
    op.add_column("contracts", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column("contracts", sa.Column("notice_period_months", sa.Integer(), nullable=True))
    op.add_column("contracts", sa.Column("annual_value", sa.Numeric(12, 2), nullable=True))


def downgrade():
    op.drop_column("contracts", "annual_value")
    op.drop_column("contracts", "notice_period_months")
    op.drop_column("contracts", "end_date")
    op.drop_column("contracts", "contract_partner")
