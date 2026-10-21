"""Evaluate historical JSON projection once per latest state, preserving scope."""
from alembic import op
import sqlalchemy as sa

revision = '0024_history_materialization'
down_revision = '0023_human_mfa'
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != 'postgresql':
        return
    definition = connection.scalar(sa.text("SELECT pg_get_functiondef('ohvr_security.financial_history(timestamp)'::regprocedure)"))
    expected = 'WITH latest AS ('
    if not definition or definition.count(expected) != 1:
        raise RuntimeError('Unexpected financial history definition; explicit forward review required')
    # Keep signature, owner, grants, principal checks, historical population,
    # unknown/zero semantics and cutoff checks. Avoid repeatedly parsing JSON
    # for every reference to the projected state after planner CTE inlining.
    connection.exec_driver_sql(definition.replace(expected, 'WITH latest AS MATERIALIZED ('))


def downgrade():
    raise RuntimeError('Forward only: retain verified historical query behavior')
