"""Track contract reviews under section 2b UStG."""
from alembic import op
import sqlalchemy as sa

revision = "0011_contract_tax_review"
down_revision = "0010_contract_financial_details"
branch_labels = None
depends_on = None


def upgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("contracts")}
    additions = (
        sa.Column("tax_review_status", sa.String(length=20), nullable=False, server_default="not_checked"),
        sa.Column("tax_review_result", sa.Text(), nullable=False, server_default=""),
        # SQLite cannot add a foreign-key constraint with ALTER TABLE ADD COLUMN.
        # The ORM still resolves the user relationship; keep this additive migration portable.
        sa.Column("tax_reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("tax_reviewed_at", sa.DateTime(), nullable=True),
    )
    for column in additions:
        if column.name not in existing:
            op.add_column("contracts", column)


def downgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("contracts")}
    for name in ("tax_reviewed_at", "tax_reviewed_by_id", "tax_review_result", "tax_review_status"):
        if name in existing:
            op.drop_column("contracts", name)
