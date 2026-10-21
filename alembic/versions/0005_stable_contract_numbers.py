"""Persist an immutable, unique registration number on each contract."""
from alembic import op
import sqlalchemy as sa

revision = "0005_stable_contract_numbers"
down_revision = "0004_contract_details"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("contracts", sa.Column(
        "contract_number", sa.String(length=32), nullable=False, server_default=""
    ))
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, created_at FROM contracts")).all()
    for contract_id, created_at in rows:
        year = getattr(created_at, "year", None)
        if year is None:
            try:
                year = int(str(created_at)[:4])
            except (TypeError, ValueError):
                year = 2026
        connection.execute(
            sa.text("UPDATE contracts SET contract_number = :number WHERE id = :id"),
            {"number": f"VR-{year}-{contract_id:04d}", "id": contract_id},
        )
    op.create_index("ux_contracts_contract_number", "contracts", ["contract_number"], unique=True)


def downgrade():
    op.drop_index("ux_contracts_contract_number", table_name="contracts")
    op.drop_column("contracts", "contract_number")
