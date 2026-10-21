"""Initial contract register schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('departments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('name'))
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'department', 'reviewer')", name='valid_user_role'),
        sa.UniqueConstraint('username'))
    op.create_table('contracts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('designation', sa.String(length=200), nullable=False),
        sa.Column('contract_type', sa.String(length=120), nullable=False),
        sa.Column('relevant_date', sa.Date(), nullable=False),
        sa.Column('date_description', sa.String(length=80), nullable=False),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('contact_person', sa.String(length=160), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False))
    op.create_index('ix_contracts_department_archived', 'contracts', ['department_id', 'archived_at'])
    op.create_table('login_sessions',
        sa.Column('token_hash', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('csrf_token', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False))
    op.create_table('login_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_login_attempts_key_hash', 'login_attempts', ['key_hash'])
    op.create_table('revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('contract_id', sa.Integer(), sa.ForeignKey('contracts.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('before', sa.JSON(), nullable=True),
        sa.Column('after', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_revisions_contract_id', 'revisions', ['contract_id'])


def downgrade():
    op.drop_index('ix_revisions_contract_id', table_name='revisions')
    op.drop_table('revisions')
    op.drop_index('ix_login_attempts_key_hash', table_name='login_attempts')
    op.drop_table('login_attempts')
    op.drop_table('login_sessions')
    op.drop_index('ix_contracts_department_archived', table_name='contracts')
    op.drop_table('contracts')
    op.drop_table('users')
    op.drop_table('departments')
