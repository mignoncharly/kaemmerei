"""Track automatic contract renewal intervals."""
from alembic import op
import sqlalchemy as sa

revision = "0008_contract_renewal"
down_revision = "0007_contract_deputy"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("contracts", sa.Column(
        "automatic_renewal", sa.Boolean(), nullable=False, server_default=sa.false()
    ))
    op.add_column("contracts", sa.Column("renewal_period_months", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("contracts", "renewal_period_months")
    op.drop_column("contracts", "automatic_renewal")
