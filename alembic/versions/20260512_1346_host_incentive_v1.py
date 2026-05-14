"""host_incentive_v1

Revision ID: d38eae3f0193
Revises: 242ae21a49ef
Create Date: 2026-05-12 13:46:03.885477+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd38eae3f0193'
down_revision: Union[str, None] = '242ae21a49ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- credits ----------------------------------------------------------
    op.create_table(
        'credits',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('amount_krw', sa.Integer(), nullable=True),
        sa.Column('percent_off', sa.Integer(), nullable=True),
        sa.Column('max_discount_krw', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('source_room_id', sa.UUID(), nullable=True),
        sa.Column('source_user_id', sa.UUID(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_on_application_id', sa.UUID(), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_room_id'], ['rooms.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['used_on_application_id'], ['room_applications.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_credits_status'), 'credits', ['status'], unique=False)
    op.create_index(op.f('ix_credits_user_id'), 'credits', ['user_id'], unique=False)

    # ---- match_results / rooms --------------------------------------------
    op.add_column('match_results', sa.Column('visible_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('rooms', sa.Column('payment_instructions', sa.Text(), nullable=True))

    # ---- users ------------------------------------------------------------
    # 1) Add nullable so backfill can land.
    op.add_column('users', sa.Column('referral_code', sa.String(length=8), nullable=True))
    op.add_column('users', sa.Column('referred_by_user_id', sa.UUID(), nullable=True))
    op.add_column(
        'users',
        sa.Column('referral_bonus_emitted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )

    # 2) Backfill referral_code for existing users (6 char base36 from md5).
    #    Using md5 hash for determinism + uniqueness with very high probability.
    op.execute(
        """
        UPDATE users
        SET referral_code = upper(substr(md5(id::text), 1, 6))
        WHERE referral_code IS NULL
        """
    )

    # 3) Indexes + FK
    op.create_index(op.f('ix_users_referral_code'), 'users', ['referral_code'], unique=True)
    op.create_index(op.f('ix_users_referred_by_user_id'), 'users', ['referred_by_user_id'], unique=False)
    op.create_foreign_key(
        'users_referred_by_user_id_fkey',
        'users',
        'users',
        ['referred_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # 4) Drop the temporary server_default on referral_bonus_emitted (we want
    #    application-level defaults, not DB-level).
    op.alter_column('users', 'referral_bonus_emitted', server_default=None)


def downgrade() -> None:
    op.drop_constraint('users_referred_by_user_id_fkey', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_referred_by_user_id'), table_name='users')
    op.drop_index(op.f('ix_users_referral_code'), table_name='users')
    op.drop_column('users', 'referral_bonus_emitted')
    op.drop_column('users', 'referred_by_user_id')
    op.drop_column('users', 'referral_code')
    op.drop_column('rooms', 'payment_instructions')
    op.drop_column('match_results', 'visible_at')
    op.drop_index(op.f('ix_credits_user_id'), table_name='credits')
    op.drop_index(op.f('ix_credits_status'), table_name='credits')
    op.drop_table('credits')
