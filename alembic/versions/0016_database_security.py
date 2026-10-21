"""Fail-closed PostgreSQL RLS and append-only audit; SQLite has no RLS."""
from pathlib import Path
from alembic import op
import sqlalchemy as sa

revision = '0016_database_security'
down_revision = '0015_schema_integrity'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('identity_audit', sa.Column('outcome', sa.String(16), nullable=False, server_default='success'))
    op.add_column('identity_audit', sa.Column('correlation_id', sa.String(64), nullable=True))
    op.create_table('security_events', sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT')),
        sa.Column('token_id',sa.Integer(),sa.ForeignKey('integration_tokens.id',ondelete='RESTRICT')),
        sa.Column('principal',sa.String(16),nullable=False),sa.Column('action',sa.String(64),nullable=False),
        sa.Column('target',sa.String(120),nullable=False),sa.Column('contract_id',sa.Integer()),
        sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('outcome',sa.String(16),nullable=False),
        sa.Column('correlation_id',sa.String(64),nullable=False),sa.Column('details',sa.JSON(),nullable=False))
    connection=op.get_bind()
    # Old rows retain unknown correlation; known denied action names keep their
    # outcome rather than being relabeled as successful by the column default.
    connection.execute(sa.text("UPDATE identity_audit SET outcome=CASE WHEN action LIKE '%!_denied' ESCAPE '!' THEN 'denied' ELSE 'success' END"))
    if connection.dialect.name=='sqlite':
        for table in ('revisions','identity_audit','security_events'):
            for action in ('UPDATE','DELETE'):
                connection.exec_driver_sql(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Append-only audit record'); END")
        for table in ('contracts','contract_documents','contract_tasks','contract_reviews'):
            for action in ('INSERT','UPDATE','DELETE'):
                row='OLD' if action=='DELETE' else 'NEW'
                cid=f'{row}.id' if table=='contracts' else f'{row}.contract_id'
                connection.exec_driver_sql(f"""CREATE TRIGGER {table}_event_{action.lower()} AFTER {action} ON {table} BEGIN
                 INSERT INTO security_events(actor_id,principal,action,target,contract_id,created_at,outcome,correlation_id,details)
                 VALUES(ohvr_actor(),CASE WHEN ohvr_actor() IS NULL THEN 'migration' ELSE 'user' END,'{action}',
                 '{table}:'||{row}.id,{cid},strftime('%Y-%m-%d %H:%M:%f','now'),'success',ohvr_correlation(),
                 json_object('table','{table}','operation','{action}')); END""")
        # SQLite audit is application authorization only. No RLS claim.
        return
    sql=(Path(__file__).resolve().parents[1]/'sql'/'0016_security.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(sql)
    owner="current_user = (SELECT r.rolname FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='ohvr_security')"
    rules={
      'contracts':('ohvr_security.read_department(department_id)',
                   'ohvr_security.write_department(department_id) AND archived_at IS NULL',
                   'ohvr_security.write_department(department_id)'),
      'contract_documents':('ohvr_security.read_contract(contract_id)','ohvr_security.write_contract(contract_id)','ohvr_security.write_contract(contract_id)'),
      'contract_tasks':('ohvr_security.read_contract(contract_id)','ohvr_security.write_contract(contract_id)','ohvr_security.write_contract(contract_id)'),
      'contract_reviews':('ohvr_security.read_contract(contract_id)','ohvr_security.decide(contract_id,team_id,assigned_user_id)','ohvr_security.decide(contract_id,team_id,assigned_user_id)'),
      'revisions':('ohvr_security.read_contract(contract_id)','false','ohvr_security.append_revision(contract_id) AND actor_id=ohvr_security.uid()'),
      'users':("ohvr_security.principal()->>'kind' IN ('guest','user')",'ohvr_security.admin() OR id=ohvr_security.uid()','ohvr_security.admin() OR id=ohvr_security.uid()'),
      'login_sessions':("token_hash=current_setting('ohvr.session_hash',true) OR user_id=ohvr_security.uid() OR ohvr_security.admin()",
                        'user_id=ohvr_security.uid() OR ohvr_security.admin() OR token_hash=current_setting(\'ohvr.session_hash\',true)',
                        "ohvr_security.role_kind()='web' AND (user_id IS NULL OR user_id=ohvr_security.uid() OR ohvr_security.principal()->>'kind'='guest' OR ohvr_security.admin())"),
      'integration_tokens':("ohvr_security.admin() OR (ohvr_security.principal()->>'kind'='token' AND id=(ohvr_security.principal()->>'id')::integer)",
                           "ohvr_security.admin() OR (ohvr_security.principal()->>'kind'='token' AND id=(ohvr_security.principal()->>'id')::integer)",
                           "ohvr_security.admin() OR (ohvr_security.principal()->>'kind'='token' AND id=(ohvr_security.principal()->>'id')::integer)"),
      'departments':("ohvr_security.role_kind()='web' OR (ohvr_security.principal()->>'kind'='token' AND ohvr_security.read_department(id))",'ohvr_security.admin()','ohvr_security.admin()'),
      'contact_identities':("ohvr_security.principal()->>'kind'='user' AND (department_id IS NULL OR ohvr_security.read_department(department_id))",'ohvr_security.admin()','ohvr_security.admin()'),
      'recipient_teams':('ohvr_security.admin() OR ohvr_security.member(id)','ohvr_security.admin()','ohvr_security.admin()'),
      'recipient_memberships':('ohvr_security.admin() OR user_id=ohvr_security.uid()','ohvr_security.admin()','ohvr_security.admin()'),
      'identity_guard':("ohvr_security.role_kind()='web'","ohvr_security.role_kind()='web'","ohvr_security.role_kind()='web'"),
      'login_attempts':("ohvr_security.role_kind()='web'","ohvr_security.role_kind()='web'","ohvr_security.role_kind()='web'"),
      'identity_audit':('ohvr_security.admin() OR actor_id=ohvr_security.uid()','false',"ohvr_security.role_kind()='web' AND ohvr_security.uid() IS NOT NULL"),
      'security_events':('ohvr_security.admin() OR (contract_id IS NOT NULL AND ohvr_security.read_contract(contract_id))','false','false')}
    for table,(read,write,check) in rules.items():
        connection.exec_driver_sql(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        connection.exec_driver_sql(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        trusted=owner
        if table in ('revisions','identity_audit','security_events'):
            trusted+=f" OR current_user=(SELECT r.rolname FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner WHERE c.oid='public.{table}'::regclass)"
        # CASE is intentional: definer functions must not recursively evaluate
        # principal() while reading their own protected bootstrap tables.
        permit=lambda expression: f'CASE WHEN {trusted} THEN true ELSE ({expression}) END'
        connection.exec_driver_sql(f'CREATE POLICY scoped_read ON public.{table} FOR SELECT USING ({permit(read)})')
        insert=check
        if table=='contract_reviews': insert='ohvr_security.write_contract(contract_id) AND created_by_id=ohvr_security.uid()'
        if table=='users': insert='ohvr_security.admin()'
        if table=='contracts': insert+=' AND created_by_id=ohvr_security.uid() AND updated_by_id=ohvr_security.uid()'
        connection.exec_driver_sql(f'CREATE POLICY scoped_insert ON public.{table} FOR INSERT WITH CHECK ({permit(insert)})')
        connection.exec_driver_sql(f'CREATE POLICY scoped_update ON public.{table} FOR UPDATE USING ({permit(write)}) WITH CHECK ({permit(check)})')
        delete=write if table in ('login_sessions','login_attempts','recipient_memberships') else 'false'
        connection.exec_driver_sql(f'CREATE POLICY scoped_delete ON public.{table} FOR DELETE USING ({permit(delete)})')
    for table in ('revisions','identity_audit','security_events'):
        connection.exec_driver_sql(f'CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON public.{table} FOR EACH ROW EXECUTE FUNCTION ohvr_security.immutable_audit()')
    for table in ('contracts','contract_documents','contract_tasks','contract_reviews'):
        connection.exec_driver_sql(f'CREATE TRIGGER capture_event AFTER INSERT OR UPDATE OR DELETE ON public.{table} FOR EACH ROW EXECUTE FUNCTION ohvr_security.capture_event()')


def downgrade():
    raise RuntimeError('Security migration is forward-only; never disable RLS as rollback')
