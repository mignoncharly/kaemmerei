"""Evaluate the unchanged department read rule once per statement population."""
from alembic import op
import sqlalchemy as sa

revision = '0022_read_admission'
down_revision = '0021_availability'
branch_labels = depends_on = None


def upgrade():
    op.create_index('ix_contracts_archived_end', 'contracts', ['archived_at','end_date'])
    connection = op.get_bind()
    if connection.dialect.name != 'postgresql':
        return
    connection.exec_driver_sql("""CREATE FUNCTION ohvr_security.read_departments()
        RETURNS integer[] LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $$
        SELECT coalesce(array_agg(d.id),'{}'::integer[]) FROM public.departments d
        WHERE ohvr_security.read_department(d.id)
        $$""")
    connection.exec_driver_sql('REVOKE ALL ON FUNCTION ohvr_security.read_departments() FROM PUBLIC')
    # Preserve the owner CASE and every other expression. Only replace the
    # per-contract invocation with an uncorrelated, statement-scoped initplan.
    # read_departments uses the exact existing rule, including forced-password,
    # token scoping and principal validation; it never grants UPDATE access.
    expression = connection.scalar(sa.text("""SELECT qual FROM pg_policies
        WHERE schemaname='public' AND tablename='contracts' AND policyname='scoped_read'"""))
    expected = 'ohvr_security.read_department(department_id)'
    if not expression or expression.count(expected) != 1:
        raise RuntimeError('Unexpected contract SELECT policy; require explicit forward repair')
    expression = expression.replace(expected,
        'department_id = ANY((SELECT ohvr_security.read_departments())::integer[])')
    connection.exec_driver_sql('ALTER POLICY scoped_read ON public.contracts USING ('+expression+')')
    # Existing deployments must deliberately rerun configure_database_roles after
    # migration; do not infer or create global role names in a migration.


def downgrade():
    raise RuntimeError('Forward only: preserve verified read policy and indexes')
