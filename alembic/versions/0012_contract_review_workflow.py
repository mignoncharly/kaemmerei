"""Add internal contract review and approval workflow."""
from alembic import op
import sqlalchemy as sa

revision = "0012_contract_review_workflow"
down_revision = "0011_contract_tax_review"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipient", sa.String(length=80), nullable=False),
        sa.Column("recipient_detail", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("result_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contract_reviews_contract_id", "contract_reviews", ["contract_id"])


def downgrade():
    op.drop_index("ix_contract_reviews_contract_id", table_name="contract_reviews")
    op.drop_table("contract_reviews")
