"""Evaluate unchanged child read authority once per statement population."""
from alembic import op
import sqlalchemy as sa

revision='0027_child_read_admission'
down_revision='0026_history_projection'
branch_labels=depends_on=None


def upgrade():
    connection=op.get_bind()
    if connection.dialect.name!='postgresql':return
    connection.exec_driver_sql("""CREATE FUNCTION ohvr_security.read_contract_ids()
      RETURNS integer[] LANGUAGE sql STABLE SECURITY DEFINER
      SET search_path=pg_catalog,pg_temp AS $$
      SELECT coalesce(array_agg(c.id),'{}'::integer[])
      FROM public.contracts c WHERE c.department_id=ANY(
        (SELECT ohvr_security.read_departments())::integer[])
      $$""")
    connection.exec_driver_sql('REVOKE ALL ON FUNCTION ohvr_security.read_contract_ids() FROM PUBLIC')
    for table in ('contract_documents','contract_tasks','contract_reviews','revisions',
                  'review_decisions','document_jobs','security_events'):
        expression=connection.scalar(sa.text("SELECT qual FROM pg_policies WHERE schemaname='public' AND tablename=:table AND policyname='scoped_read'"),{'table':table})
        expected='ohvr_security.read_contract(contract_id)'
        if not expression or expression.count(expected)!=1:
            raise RuntimeError('Unexpected child SELECT policy; explicit forward review required')
        replacement='contract_id = ANY((SELECT ohvr_security.read_contract_ids())::integer[])'
        expression=expression.replace(expected,replacement)
        # Preserve owner CASE, admin exceptions, NULL handling and every other
        # expression. Never change mutation policies or grant UPDATE/DELETE.
        connection.exec_driver_sql('ALTER POLICY scoped_read ON public.'+table+' USING ('+expression+')')


def downgrade():
    raise RuntimeError('Forward only: preserve verified scoped read policy')
