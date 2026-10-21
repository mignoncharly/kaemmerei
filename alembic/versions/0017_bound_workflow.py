"""Version-bound workflow with explicit legacy provenance; forward only."""
from alembic import op
import sqlalchemy as sa

revision='0017_bound_workflow'
down_revision='0016_database_security'
branch_labels=depends_on=None


def upgrade():
    for column in (sa.Column('content_revision',sa.Integer(),nullable=False,server_default='1'),
                   sa.Column('material_actor_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT')),
                   sa.Column('approval_provenance',sa.String(24),nullable=False,server_default='legacy_unverified'),
                   sa.Column('tax_provenance',sa.String(24),nullable=False,server_default='legacy_unverified')):
        if column.name=='material_actor_id':
            with op.batch_alter_table('contracts') as batch:
                batch.add_column(sa.Column('material_actor_id',sa.Integer()))
                batch.create_foreign_key('fk_material_actor','users',['material_actor_id'],['id'],ondelete='RESTRICT')
                batch.alter_column('status',existing_type=sa.String(20),existing_nullable=False,server_default='draft')
        else:
            op.add_column('contracts',column)
    for table in ('contract_tasks','contract_reviews'):
        op.add_column(table,sa.Column('version',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('contract_reviews',sa.Column('content_revision',sa.Integer()))
    op.add_column('contract_reviews',sa.Column('provenance',sa.String(24),nullable=False,server_default='legacy_unverified'))
    op.create_table('review_decisions',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contracts.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('review_id',sa.Integer(),sa.ForeignKey('contract_reviews.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('review_version',sa.Integer(),nullable=False),sa.Column('content_revision',sa.Integer(),nullable=False),
        sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('team_id',sa.Integer(),sa.ForeignKey('recipient_teams.id',ondelete='RESTRICT')),
        sa.Column('assigned_user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT')),
        sa.Column('status',sa.String(24),nullable=False),sa.Column('reason',sa.Text(),nullable=False),
        sa.Column('decided_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('review_id','review_version',name='unique_review_decision'))
    c=op.get_bind()
    if c.dialect.name=='sqlite':
        # Batch rebuilding contracts drops its triggers. Restore its event triggers.
        for action in ('INSERT','UPDATE','DELETE'):
            row='OLD' if action=='DELETE' else 'NEW'
            c.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS contracts_event_{action.lower()} AFTER {action} ON contracts BEGIN
              INSERT INTO security_events(actor_id,principal,action,target,contract_id,created_at,outcome,correlation_id,details)
              VALUES(ohvr_actor(),CASE WHEN ohvr_actor() IS NULL THEN 'migration' ELSE 'user' END,'{action}','contracts:'||{row}.id,{row}.id,
              strftime('%Y-%m-%d %H:%M:%f','now'),'success',ohvr_correlation(),json_object('table','contracts','operation','{action}')); END""")
        for action in ('UPDATE','DELETE'):
            c.exec_driver_sql(f"CREATE TRIGGER decisions_no_{action.lower()} BEFORE {action} ON review_decisions BEGIN SELECT RAISE(ABORT,'Immutable decision'); END")
        for table in ('contract_tasks','contract_reviews','contract_documents'):
            for action in ('INSERT','UPDATE','DELETE'):
                row='OLD' if action=='DELETE' else 'NEW'
                c.exec_driver_sql(f"CREATE TRIGGER {table}_archive_{action.lower()} BEFORE {action} ON {table} WHEN EXISTS(SELECT 1 FROM contracts WHERE id={row}.contract_id AND archived_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'Archived aggregate'); END")
        c.exec_driver_sql("CREATE TRIGGER contracts_archive_guard BEFORE UPDATE ON contracts WHEN OLD.archived_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'Archived aggregate'); END")
        return
    owner="current_user=(SELECT r.rolname FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner WHERE n.nspname='ohvr_security')"
    c.exec_driver_sql('ALTER TABLE review_decisions ENABLE ROW LEVEL SECURITY')
    c.exec_driver_sql('ALTER TABLE review_decisions FORCE ROW LEVEL SECURITY')
    c.exec_driver_sql(f'CREATE POLICY migration_access ON review_decisions FOR ALL USING ({owner}) WITH CHECK ({owner})')
    c.exec_driver_sql(f'CREATE POLICY scoped_read ON review_decisions FOR SELECT USING (CASE WHEN {owner} THEN true ELSE ohvr_security.read_contract(contract_id) END)')
    c.exec_driver_sql(f'CREATE POLICY scoped_insert ON review_decisions FOR INSERT WITH CHECK (CASE WHEN {owner} THEN true ELSE actor_id=ohvr_security.uid() AND ohvr_security.decide(contract_id,team_id,assigned_user_id) END)')
    c.exec_driver_sql('CREATE TRIGGER immutable_decision BEFORE UPDATE OR DELETE ON review_decisions FOR EACH ROW EXECUTE FUNCTION ohvr_security.immutable_audit()')
    c.exec_driver_sql("""CREATE FUNCTION ohvr_security.archive_barrier() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
     SET search_path=pg_catalog,pg_temp AS $$ DECLARE archived timestamp; BEGIN
      IF TG_TABLE_NAME='contracts' THEN
       IF OLD.archived_at IS NOT NULL THEN RAISE EXCEPTION 'Archived aggregate' USING ERRCODE='42501'; END IF;
      ELSE
       SELECT archived_at INTO archived FROM public.contracts WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.contract_id ELSE NEW.contract_id END FOR UPDATE;
       IF archived IS NOT NULL THEN RAISE EXCEPTION 'Archived aggregate' USING ERRCODE='42501'; END IF;
      END IF;
      RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
     END $$""")
    c.exec_driver_sql('REVOKE ALL ON FUNCTION ohvr_security.archive_barrier() FROM PUBLIC')
    for table in ('contract_tasks','contract_reviews','contract_documents'):
        c.exec_driver_sql(f'CREATE TRIGGER archive_barrier BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION ohvr_security.archive_barrier()')
    c.exec_driver_sql('CREATE TRIGGER archive_barrier BEFORE UPDATE ON contracts FOR EACH ROW EXECUTE FUNCTION ohvr_security.archive_barrier()')
    for policy in ('scoped_update',):
        c.exec_driver_sql(f'DROP POLICY {policy} ON contract_reviews')
        c.exec_driver_sql(f'CREATE POLICY {policy} ON contract_reviews FOR UPDATE USING (CASE WHEN {owner} THEN true ELSE ohvr_security.decide(contract_id,team_id,assigned_user_id) OR ohvr_security.write_contract(contract_id) END) WITH CHECK (CASE WHEN {owner} THEN true ELSE ohvr_security.decide(contract_id,team_id,assigned_user_id) OR ohvr_security.write_contract(contract_id) END)')
    c.exec_driver_sql("""CREATE OR REPLACE FUNCTION ohvr_security.protect_review() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
     SET search_path=pg_catalog,pg_temp AS $$ BEGIN
      IF session_user=(SELECT r.rolname FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner WHERE n.nspname='ohvr_security') OR ohvr_security.admin() THEN RETURN NEW; END IF;
      IF ohvr_security.write_contract(NEW.contract_id) AND NEW.status='open' AND NEW.result_text='' AND NEW.provenance='superseded'
       AND NEW.content_revision IS DISTINCT FROM OLD.content_revision
       AND NEW.content_revision=(SELECT content_revision FROM public.contracts WHERE id=NEW.contract_id)
       AND (to_jsonb(NEW)-ARRAY['status','result_text','provenance','content_revision','version'])=(to_jsonb(OLD)-ARRAY['status','result_text','provenance','content_revision','version']) THEN RETURN NEW; END IF;
      IF NOT ohvr_security.decide(OLD.contract_id,OLD.team_id,OLD.assigned_user_id)
       OR (to_jsonb(NEW)-ARRAY['status','result_text','updated_by_id','updated_at','version','content_revision','provenance']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','result_text','updated_by_id','updated_at','version','content_revision','provenance'])
       OR NEW.updated_by_id IS DISTINCT FROM ohvr_security.uid() THEN RAISE EXCEPTION 'Review mutation denied' USING ERRCODE='42501'; END IF;
      RETURN NEW; END $$""")


def downgrade():
    raise RuntimeError('Forward-only workflow recovery; preserve decisions and legacy provenance')
