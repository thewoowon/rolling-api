"""host_planner_split

Revision ID: 242ae21a49ef
Revises: d690e216c8c4
Create Date: 2026-05-11 14:13:02.051549+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '242ae21a49ef'
down_revision: Union[str, None] = 'd690e216c8c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add host_user_id as nullable so existing rows can be backfilled.
    op.add_column('rooms', sa.Column('host_user_id', sa.UUID(), nullable=True))
    op.add_column('rooms', sa.Column('viable_at', sa.DateTime(timezone=True), nullable=True))

    # 2. Backfill host_user_id from existing planner.user_id
    op.execute(
        """
        UPDATE rooms
        SET host_user_id = planners.user_id
        FROM planners
        WHERE rooms.planner_id = planners.id
          AND rooms.host_user_id IS NULL
        """
    )

    # 3. Lock host_user_id as NOT NULL
    op.alter_column('rooms', 'host_user_id', existing_type=sa.UUID(), nullable=False)

    # 4. planner_id becomes nullable (rooms can be pre-assignment).
    op.alter_column('rooms', 'planner_id', existing_type=sa.UUID(), nullable=True)

    op.create_index(op.f('ix_rooms_host_user_id'), 'rooms', ['host_user_id'], unique=False)

    # 5. Replace planner_id FK ON DELETE RESTRICT → SET NULL
    op.drop_constraint(op.f('rooms_planner_id_fkey'), 'rooms', type_='foreignkey')
    op.create_foreign_key(
        'rooms_planner_id_fkey',
        'rooms',
        'planners',
        ['planner_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # 6. host_user_id FK
    op.create_foreign_key(
        'rooms_host_user_id_fkey',
        'rooms',
        'users',
        ['host_user_id'],
        ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint('rooms_host_user_id_fkey', 'rooms', type_='foreignkey')
    op.drop_constraint('rooms_planner_id_fkey', 'rooms', type_='foreignkey')
    op.create_foreign_key(
        op.f('rooms_planner_id_fkey'),
        'rooms',
        'planners',
        ['planner_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.drop_index(op.f('ix_rooms_host_user_id'), table_name='rooms')
    op.alter_column('rooms', 'planner_id', existing_type=sa.UUID(), nullable=False)
    op.drop_column('rooms', 'viable_at')
    op.drop_column('rooms', 'host_user_id')
