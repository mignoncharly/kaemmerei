"""Add contract task tracking."""
from alembic import op
import sqlalchemy as sa

revision = "0009_contract_tasks"
down_revision = "0008_contract_renewal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('review', 'complete', 'update', 'other')", name="valid_task_kind"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'done')", name="valid_task_status"),
    )
    op.create_index("ix_contract_tasks_contract_id", "contract_tasks", ["contract_id"])


def downgrade():
    op.drop_index("ix_contract_tasks_contract_id", table_name="contract_tasks")
    op.drop_table("contract_tasks")
