"""Add scoped read-only API credentials for external applications."""
from alembic import op
import sqlalchemy as sa

revision = "0013_integration_tokens"
down_revision = "0012_contract_review_workflow"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "integration_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("token_prefix", name="uq_integration_tokens_token_prefix"),
        sa.UniqueConstraint("token_hash", name="uq_integration_tokens_token_hash"),
    )


def downgrade():
    op.drop_table("integration_tokens")
