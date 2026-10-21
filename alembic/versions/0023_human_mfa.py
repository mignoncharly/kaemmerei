"""Encrypted TOTP enrollment and independently scoped challenge sessions."""
from pathlib import Path
from alembic import op
import sqlalchemy as sa

revision='0023_human_mfa'
down_revision='0022_read_admission'
branch_labels=depends_on=None


def upgrade():
    with op.batch_alter_table('login_sessions') as batch:
        batch.add_column(sa.Column('pending_user_id',sa.Integer(),nullable=True))
        batch.create_foreign_key('fk_login_session_pending_user','users',['pending_user_id'],['id'],ondelete='CASCADE')
        batch.add_column(sa.Column('mfa_verified',sa.Boolean(),nullable=False,server_default=sa.false()))
        batch.add_column(sa.Column('mfa_attempts',sa.Integer(),nullable=False,server_default='0'))
        batch.create_index('ix_login_sessions_user_id',['user_id'])
        batch.create_index('ix_login_sessions_pending_user_id',['pending_user_id'])
    op.create_table('mfa_credentials',
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('seed_ciphertext',sa.Text(),nullable=True),
        sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('last_step',sa.Integer(),nullable=False,server_default='-1'),
        sa.Column('authorization_expires_at',sa.DateTime(),nullable=True),
        sa.CheckConstraint('last_step >= -1',name='mfa_step_nonnegative'))
    policy=op.create_table('mfa_policy',sa.Column('id',sa.Integer(),primary_key=True,autoincrement=False),
        sa.Column('required',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.CheckConstraint('id = 1',name='mfa_single_policy'))
    # Deliberate owner command enables rollout/revokes sessions; migrating a
    # business database must not silently enroll users or invent seed/key data.
    op.bulk_insert(policy,[dict(id=1,required=False)])
    connection=op.get_bind()
    if connection.dialect.name!='postgresql':
        return
    connection.exec_driver_sql((Path(__file__).resolve().parents[1]/'sql'/'0023_mfa.sql').read_text(encoding='utf-8').replace('%','%%'))
    resolver=connection.scalar(sa.text("SELECT pg_get_functiondef('ohvr_security.resolve_principal()'::regprocedure)"))
    expected='AND (s.user_id IS NULL OR (u.is_active'
    if resolver.count(expected)!=1:
        raise RuntimeError('Unexpected principal resolver; explicit forward review required')
    resolver=resolver.replace(expected,"""AND (s.user_id IS NULL OR s.mfa_verified OR NOT (
      ohvr_security.mfa_policy_required() OR EXISTS(
       SELECT 1 FROM public.mfa_credentials mf WHERE mf.user_id=s.user_id AND mf.enabled)))
    AND (s.user_id IS NULL OR (u.is_active""")
    connection.exec_driver_sql(resolver)
    # A fully authenticated user can revoke their own other pending challenges
    # on password change. Guests still see/revoke only their exact cookie hash.
    for name in ('scoped_read','scoped_update','scoped_delete'):
        expr=connection.scalar(sa.text("SELECT qual FROM pg_policies WHERE schemaname='public' AND tablename='login_sessions' AND policyname=:name"),{'name':name})
        expected='user_id = ohvr_security.uid()'
        if not expr or expr.count(expected)!=1:
            raise RuntimeError('Unexpected session scope policy; require explicit forward review')
        expr=expr.replace(expected,'(user_id = ohvr_security.uid() OR pending_user_id = ohvr_security.uid())')
        connection.exec_driver_sql('ALTER POLICY '+name+' ON public.login_sessions USING ('+expr+')')


def downgrade():
    raise RuntimeError('Forward only: preserve human MFA and recovery audit')
