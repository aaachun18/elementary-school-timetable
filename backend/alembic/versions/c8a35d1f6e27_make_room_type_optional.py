"""make rooms.room_type optional

Task 98: rooms no longer have a type -- a requirement names the one special
room it needs (class_subject_requirements.required_room_id), and a
教學組長 only keeps a room's name. The column stays (with its data), but new
rooms leave it empty.

Revision ID: c8a35d1f6e27
Revises: b4f71c2e9a05
Create Date: 2026-10-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a35d1f6e27'
down_revision: Union[str, Sequence[str], None] = 'b4f71c2e9a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNKNOWN_ROOM_TYPE = '未分類'


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('rooms', 'room_type', existing_type=sa.String(length=100), nullable=True)


def downgrade() -> None:
    """Downgrade schema. Rooms created without a type get a placeholder."""
    op.execute(
        sa.text('UPDATE rooms SET room_type = :placeholder WHERE room_type IS NULL').bindparams(
            placeholder=UNKNOWN_ROOM_TYPE
        )
    )
    op.alter_column('rooms', 'room_type', existing_type=sa.String(length=100), nullable=False)
