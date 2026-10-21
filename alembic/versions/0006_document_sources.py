"""Support additional file types and links to an external document system."""
from alembic import op
import sqlalchemy as sa

revision = "0006_document_sources"
down_revision = "0005_stable_contract_numbers"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contract_documents") as batch_op:
        batch_op.alter_column("storage_key", existing_type=sa.String(length=40), nullable=True)
        batch_op.add_column(sa.Column(
            "content_type", sa.String(length=120), nullable=False, server_default="application/pdf"
        ))
        batch_op.add_column(sa.Column("external_url", sa.String(length=2048), nullable=True))


def downgrade():
    with op.batch_alter_table("contract_documents") as batch_op:
        batch_op.drop_column("external_url")
        batch_op.drop_column("content_type")
        batch_op.alter_column("storage_key", existing_type=sa.String(length=40), nullable=False)
