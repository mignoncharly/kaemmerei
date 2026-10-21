"""Inventory legacy exceptions, then enforce schema invariants without guessing repairs."""
from alembic import op
import sqlalchemy as sa
from app.schema_rules import RULES, inventory

revision = '0015_schema_integrity'
down_revision = '0014_identity_authorization'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    problems = inventory(connection)
    if problems:
        import json
        raise RuntimeError('Reviewed legacy repairs required before schema migration: ' + json.dumps(problems))
    for table, rules in RULES.items():
        existing = {c['name'] for c in sa.inspect(connection).get_check_constraints(table)}
        with op.batch_alter_table(table) as batch:
            for name, expression in rules.items():
                if name not in existing:
                    batch.create_check_constraint(name, expression)
            if table == 'contracts':
                batch.create_foreign_key('fk_contract_tax_reviewer', 'users', ['tax_reviewed_by_id'], ['id'], ondelete='SET NULL')


def downgrade():
    raise RuntimeError('Forward-only integrity migration; use reviewed recovery')
