"""Append operator audit records through the existing audit-owner RLS policy."""
from alembic import op
import sqlalchemy as sa

revision = '0028_operator_audit'
down_revision = '0027_child_read_admission'
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != 'postgresql':
        return
    connection.exec_driver_sql("""
      CREATE FUNCTION ohvr_security.append_operator_audit(event_action text, event_target text, event_details jsonb)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,pg_temp AS $$
      BEGIN
        IF session_user IS DISTINCT FROM
          (SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='ohvr_security')
          OR ohvr_security.role_kind() IS NOT NULL THEN
          RAISE EXCEPTION 'Operator audit requires the migration owner' USING ERRCODE='42501';
        END IF;
        IF event_action IS NULL OR length(event_action) NOT BETWEEN 1 AND 64
          OR event_target IS NULL OR length(event_target) NOT BETWEEN 1 AND 120
          OR jsonb_typeof(event_details) IS DISTINCT FROM 'object' THEN
          RAISE EXCEPTION 'Invalid operator audit record' USING ERRCODE='22023';
        END IF;
        INSERT INTO public.identity_audit(actor_id,principal,action,target,details,created_at,outcome)
        VALUES(NULL,'operator',event_action,event_target,event_details,
          timezone('UTC',statement_timestamp()),
          CASE WHEN event_action ~ '_denied$' THEN 'denied' ELSE 'success' END);
      END $$
    """)
    signature = 'ohvr_security.append_operator_audit(text,text,jsonb)'
    connection.exec_driver_sql(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
    quote = connection.dialect.identifier_preparer.quote
    # Works both before hardening and on an already hardened 0027 deployment.
    # Membership requires SET TRUE, never inherited audit-table privileges.
    owner = connection.scalar(sa.text("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='ohvr_security'"))
    audit_owner = connection.scalar(sa.text("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.identity_audit'::regclass"))
    connection.exec_driver_sql(f'ALTER FUNCTION {signature} OWNER TO {quote(audit_owner)}')
    previous_role = connection.scalar(sa.text('SELECT current_user'))
    connection.exec_driver_sql(f'SET LOCAL ROLE {quote(audit_owner)}')
    connection.exec_driver_sql(f'GRANT EXECUTE ON FUNCTION {signature} TO {quote(owner)}')
    connection.exec_driver_sql(f'SET LOCAL ROLE {quote(previous_role)}')


def downgrade():
    raise RuntimeError('Forward only: preserve atomic operator auditing')
