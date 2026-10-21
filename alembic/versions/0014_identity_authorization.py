"""Add explicit approval/identity administration; preserve legacy display values."""
from alembic import op
import sqlalchemy as sa

revision = "0014_identity_authorization"
down_revision = "0013_integration_tokens"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('can_approve', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table('identity_guard', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('epoch', sa.Integer(), nullable=False))
    op.execute(sa.text('INSERT INTO identity_guard (id, epoch) VALUES (1, 0)'))
    op.create_table('identity_audit', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('principal', sa.String(16), nullable=False), sa.Column('action', sa.String(64), nullable=False),
        sa.Column('target', sa.String(120), nullable=False), sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('contact_identities', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('display_name', sa.String(160), nullable=False),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id', ondelete='RESTRICT')),
        sa.Column('scope_key', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index('ux_contact_scope_name', 'contact_identities', ['scope_key', 'display_name'], unique=True)
    # Scope backfilled private names to their original department; never publish
    # private contract-derived identities into the deliberately shared catalog.
    connection = op.get_bind()
    contacts = sa.table('contact_identities', sa.column('display_name'), sa.column('department_id'),
                        sa.column('scope_key'), sa.column('is_active'))
    pairs = connection.execute(sa.text("SELECT department_id, contact_person FROM contracts UNION "
                                        "SELECT department_id, deputy_contact_person FROM contracts")).all()
    for department, name in pairs:
        if name and name.strip():
            connection.execute(contacts.insert().values(display_name=name, department_id=department,
                                                       scope_key=department, is_active=True))
    op.create_table('recipient_teams', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(150), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table('recipient_memberships',
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('recipient_teams.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), primary_key=True))
    with op.batch_alter_table('contract_reviews') as batch:
        batch.add_column(sa.Column('team_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('assigned_user_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_review_team', 'recipient_teams', ['team_id'], ['id'], ondelete='RESTRICT')
        batch.create_foreign_key('fk_review_assignee', 'users', ['assigned_user_id'], ['id'], ondelete='RESTRICT')


def downgrade():
    # Explicit recovery decision required: dropping assignment/audit data is not
    # a safe routine rollback. Restore a verified compatible backup instead.
    raise RuntimeError('Identity migration is forward-only; use an approved recovery procedure')
