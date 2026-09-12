"""add lesson fixed_time_slot_id

Revision ID: 6d3e68b11338
Revises: b049ab23b45e
Create Date: 2026-09-12 22:00:04.090284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d3e68b11338'
down_revision: Union[str, Sequence[str], None] = 'b049ab23b45e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Autogenerate produced an unnamed FK (create_foreign_key(None, ...)),
    # which also makes drop_constraint(None, ...) in downgrade() invalid --
    # named explicitly here so downgrade() actually works.
    op.add_column('lessons', sa.Column('fixed_time_slot_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'lessons_fixed_time_slot_id_fkey', 'lessons', 'time_slots',
        ['fixed_time_slot_id'], ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('lessons_fixed_time_slot_id_fkey', 'lessons', type_='foreignkey')
    op.drop_column('lessons', 'fixed_time_slot_id')
