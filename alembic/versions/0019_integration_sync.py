"""Transactional outbox, serialized publication and scope-bound snapshots."""
from pathlib import Path
from alembic import op
import sqlalchemy as sa

revision='0019_integration_sync'
down_revision='0018_document_lifecycle'
branch_labels=depends_on=None


def upgrade():
    with op.batch_alter_table('integration_tokens') as b:
        for column in (
            sa.Column('api_scopes',sa.String(300),nullable=False,server_default='legacy_v1'),
            sa.Column('grant_version',sa.Integer(),nullable=False,server_default='1'),
            sa.Column('service_owner',sa.String(120)),sa.Column('owner_user_id',sa.Integer()),
            sa.Column('rotated_from_id',sa.Integer()),sa.Column('revoked_at',sa.DateTime()),
            sa.Column('revocation_reason',sa.String(200))):b.add_column(column)
        b.create_foreign_key('fk_token_owner','users',['owner_user_id'],['id'],ondelete='RESTRICT')
        b.create_foreign_key('fk_token_rotation','integration_tokens',['rotated_from_id'],['id'],ondelete='RESTRICT')
    op.create_table('sync_state',sa.Column('id',sa.Integer(),primary_key=True,autoincrement=False),sa.Column('next_seq',sa.Integer(),nullable=False),sa.Column('floor',sa.Integer(),nullable=False))
    op.execute('INSERT INTO sync_state(id,next_seq,floor) VALUES (1,0,0)')
    for name,key in (('sync_outbox','id'),('sync_events','seq')):
        columns=[sa.Column(key,sa.Integer(),primary_key=True,autoincrement=name=='sync_outbox'),
            sa.Column('event_key',sa.String(36),nullable=False,unique=True),sa.Column('contract_id',sa.Integer(),nullable=False),
            sa.Column('old_department_id',sa.Integer()),sa.Column('new_department_id',sa.Integer()),sa.Column('kind',sa.String(24),nullable=False)]
        if name=='sync_outbox':columns.append(sa.Column('published_seq',sa.Integer()))
        op.create_table(name,*columns)
    op.create_table('sync_cursors',sa.Column('key_hash',sa.String(64),primary_key=True),
        sa.Column('token_id',sa.Integer(),sa.ForeignKey('integration_tokens.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('mode',sa.String(16),nullable=False),
        sa.Column('snapshot_id',sa.String(36)),sa.Column('position',sa.Integer(),nullable=False),
        sa.Column('boundary',sa.Integer(),nullable=False),sa.Column('expires_at',sa.DateTime(),nullable=False))
    op.create_table('sync_snapshot_items',sa.Column('snapshot_id',sa.String(36),primary_key=True),
        sa.Column('position',sa.Integer(),primary_key=True,autoincrement=False),
        sa.Column('token_id',sa.Integer(),sa.ForeignKey('integration_tokens.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('contract_id',sa.Integer(),nullable=False),sa.Column('payload',sa.JSON(),nullable=False))
    c=op.get_bind()
    if c.dialect.name=='postgresql':
        c.exec_driver_sql((Path(__file__).resolve().parents[1]/'sql'/'0019_sync.sql').read_text(encoding='utf-8').replace('%','%%'))
        original=(Path(__file__).resolve().parents[1]/'sql'/'0016_security.sql').read_text(encoding='utf-8')
        resolver=original[original.index('CREATE FUNCTION ohvr_security.resolve_principal()'):original.index('CREATE FUNCTION ohvr_security.principal()')]
        resolver=resolver.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1).replace('AND (t.department_id IS NULL OR d.is_active);',"AND (t.department_id IS NULL OR d.is_active) AND t.revoked_at IS NULL AND (t.owner_user_id IS NULL OR EXISTS(SELECT 1 FROM public.users own LEFT JOIN public.departments od ON od.id=own.department_id WHERE own.id=t.owner_user_id AND own.is_active AND (own.role<>'department' OR od.is_active)));")
        c.exec_driver_sql(resolver)
        return
    # SQLite serializes writes; every emitted event is committed with its source.
    c.exec_driver_sql("""CREATE TRIGGER token_grant_change AFTER UPDATE OF api_scopes,department_id,owner_user_id,service_owner,is_active,expires_at ON integration_tokens BEGIN
      UPDATE integration_tokens SET grant_version=OLD.grant_version+1 WHERE id=NEW.id; END""")
    c.exec_driver_sql("CREATE TRIGGER sync_owner_change AFTER UPDATE OF is_active,role,department_id ON users BEGIN UPDATE integration_tokens SET grant_version=grant_version+1 WHERE owner_user_id=NEW.id; END")
    c.exec_driver_sql("CREATE TRIGGER sync_department_change AFTER UPDATE OF is_active ON departments BEGIN UPDATE integration_tokens SET grant_version=grant_version+1 WHERE department_id=NEW.id OR owner_user_id IN (SELECT id FROM users WHERE department_id=NEW.id); END")
    for action in ('INSERT','UPDATE','DELETE'):
        row='OLD' if action=='DELETE' else 'NEW'
        old='NULL' if action=='INSERT' else 'OLD.department_id'
        new='NULL' if action=='DELETE' else 'NEW.department_id'
        c.exec_driver_sql(f"""CREATE TRIGGER contracts_sync_{action.lower()} AFTER {action} ON contracts BEGIN
          INSERT INTO sync_outbox(event_key,contract_id,old_department_id,new_department_id,kind)
          VALUES(lower(hex(randomblob(16))),{row}.id,{old},{new},'contract'); END""")
    for table,kind in (('contract_documents','document'),('contract_tasks','task'),('contract_reviews','review'),('review_decisions','decision'),('revisions','history')):
        for action in ('INSERT','UPDATE','DELETE'):
            row='OLD' if action=='DELETE' else 'NEW'
            c.exec_driver_sql(f"""CREATE TRIGGER {table}_sync_{action.lower()} AFTER {action} ON {table} BEGIN
              UPDATE contracts SET updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id={row}.contract_id AND archived_at IS NULL;
              INSERT INTO sync_outbox(event_key,contract_id,old_department_id,new_department_id,kind)
              SELECT lower(hex(randomblob(16))),id,department_id,department_id,'{kind}' FROM contracts WHERE id={row}.contract_id AND archived_at IS NULL; END""")


def downgrade():
    raise RuntimeError('Forward-only synchronization migration; preserve replay and cursor state')
