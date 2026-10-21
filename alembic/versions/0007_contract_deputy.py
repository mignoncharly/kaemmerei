"""Add an optional deputy contact person to contracts."""
from alembic import op
import sqlalchemy as sa

revision = "0007_contract_deputy"
down_revision = "0006_document_sources"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("contracts", sa.Column(
        "deputy_contact_person", sa.String(length=160), nullable=False, server_default=""
    ))


def downgrade():
    op.drop_column("contracts", "deputy_contact_person")
