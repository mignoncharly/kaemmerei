"""Store metadata for uploaded contract PDFs.

Revision ID: 0003_contract_documents
Revises: 0002_contract_status
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_contract_documents"
down_revision = "0002_contract_status"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_filename", sa.String(length=200), nullable=False),
        sa.Column("storage_key", sa.String(length=40), nullable=False, unique=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contract_documents_contract_id", "contract_documents", ["contract_id"])


def downgrade():
    op.drop_index("ix_contract_documents_contract_id", table_name="contract_documents")
    op.drop_table("contract_documents")
