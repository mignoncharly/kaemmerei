"""Private document lifecycle; preserve all legacy blobs as unverified."""
from alembic import op
import sqlalchemy as sa

revision='0018_document_lifecycle'
down_revision='0017_bound_workflow'
branch_labels=depends_on=None


def upgrade():
    with op.batch_alter_table('contract_documents') as b:
        for column in (
            sa.Column('state',sa.String(24),nullable=False,server_default='legacy_unverified'),
            sa.Column('sha256',sa.String(64)),sa.Column('verified_media_type',sa.String(120)),
            sa.Column('scan_result',sa.String(24),nullable=False,server_default='unverified'),
            sa.Column('scanner_version',sa.String(200)),sa.Column('scanned_at',sa.DateTime()),
            sa.Column('provenance',sa.String(24),nullable=False,server_default='legacy_unverified'),
            sa.Column('version',sa.Integer(),nullable=False,server_default='1'),
            sa.Column('replaces_id',sa.Integer()),sa.Column('replaces_version',sa.Integer()),
            sa.Column('legal_hold',sa.Boolean(),nullable=False,server_default=sa.false()),
            sa.Column('retention_class',sa.String(40),nullable=False,server_default='unclassified')):
            b.add_column(column)
        b.create_foreign_key('fk_document_predecessor','contract_documents',['replaces_id'],['id'],ondelete='RESTRICT')
        b.create_check_constraint('document_state',"state IN ('legacy_unverified','pending','quarantined','available','rejected','superseded','disposed','link')")
    op.create_table('document_jobs',sa.Column('document_id',sa.Integer(),sa.ForeignKey('contract_documents.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contracts.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('state',sa.String(24),nullable=False,server_default='pending'),
        sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),sa.Column('last_error',sa.String(40)),
        sa.Column('updated_at',sa.DateTime(),nullable=False))
    c=op.get_bind()
    if c.dialect.name=='sqlite':
        # The batch rebuild removes document triggers; recreate both controls.
        for action in ('INSERT','UPDATE','DELETE'):
            row='OLD' if action=='DELETE' else 'NEW'
            c.exec_driver_sql(f"""CREATE TRIGGER contract_documents_event_{action.lower()} AFTER {action} ON contract_documents BEGIN
             INSERT INTO security_events(actor_id,principal,action,target,contract_id,created_at,outcome,correlation_id,details)
             VALUES(ohvr_actor(),CASE WHEN ohvr_actor() IS NULL THEN 'migration' ELSE 'user' END,'{action}',
              'contract_documents:'||{row}.id,{row}.contract_id,strftime('%Y-%m-%d %H:%M:%f','now'),'success',ohvr_correlation(),json_object('table','contract_documents','operation','{action}')); END""")
            for table in ('contract_documents','document_jobs'):
                c.exec_driver_sql(f"CREATE TRIGGER {table}_archive_{action.lower()} BEFORE {action} ON {table} WHEN EXISTS(SELECT 1 FROM contracts WHERE id={row}.contract_id AND archived_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'Archived aggregate'); END")
        # Legacy external links remain links; no remote fetching or scan claims.
        # Archived rows cannot be rewritten through the normal archive trigger.
        # Leave all legacy rows unverified, including links, for explicit review.
        return
    owner="current_user=(SELECT r.rolname FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner WHERE n.nspname='ohvr_security')"
    c.exec_driver_sql('ALTER TABLE document_jobs ENABLE ROW LEVEL SECURITY')
    c.exec_driver_sql('ALTER TABLE document_jobs FORCE ROW LEVEL SECURITY')
    c.exec_driver_sql(f'CREATE POLICY scoped_read ON document_jobs FOR SELECT USING (CASE WHEN {owner} THEN true ELSE ohvr_security.read_contract(contract_id) END)')
    c.exec_driver_sql(f'CREATE POLICY scoped_write ON document_jobs FOR ALL USING (CASE WHEN {owner} THEN true ELSE ohvr_security.write_contract(contract_id) END) WITH CHECK (CASE WHEN {owner} THEN true ELSE ohvr_security.write_contract(contract_id) END)')
    c.exec_driver_sql('CREATE TRIGGER archive_barrier BEFORE INSERT OR UPDATE OR DELETE ON document_jobs FOR EACH ROW EXECUTE FUNCTION ohvr_security.archive_barrier()')
    c.exec_driver_sql("""CREATE FUNCTION ohvr_security.document_access(doc integer, permitted boolean) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
     SET search_path=pg_catalog,pg_temp AS $$ DECLARE cid integer; p jsonb; BEGIN
      SELECT contract_id INTO cid FROM public.contract_documents WHERE id=doc;
      p:=ohvr_security.principal();
      IF ohvr_security.role_kind() NOT IN ('web','integration') OR p->>'kind' NOT IN ('user','token') OR p->>'kind' IS NULL THEN
       RAISE EXCEPTION 'Document access audit denied' USING ERRCODE='42501'; END IF;
      IF cid IS NULL OR NOT ohvr_security.read_contract(cid) THEN cid:=NULL; permitted:=false; END IF;
      INSERT INTO public.security_events(actor_id,token_id,principal,action,target,contract_id,created_at,outcome,correlation_id,details)
      VALUES(ohvr_security.uid(),CASE WHEN p->>'kind'='token' THEN (p->>'id')::integer END,p->>'kind','DOCUMENT_ACCESS','document:'||doc,cid,
       timezone('UTC',statement_timestamp()),CASE WHEN permitted THEN 'success' ELSE 'denied' END,
       COALESCE(NULLIF(current_setting('ohvr.correlation_id',true),''),gen_random_uuid()::text),jsonb_build_object('document_id',doc,'operation','download'));
     END $$""")
    c.exec_driver_sql('REVOKE ALL ON FUNCTION ohvr_security.document_access(integer,boolean) FROM PUBLIC')


def downgrade():
    raise RuntimeError('Forward-only document migration; preserve blobs, scan and retention evidence')
