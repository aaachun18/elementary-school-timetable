"""add semester_teachers.homeroom_class_id (導師 per 排課紀錄)

A participating teacher may be 導師 of one class in the record; a class has
at most one 導師 per record. Nullable: existing rows have none.

Revision ID: a4d2c6e8f310
Revises: f3c5a7e9b142
Create Date: 2026-10-21 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4d2c6e8f310'
down_revision: Union[str, Sequence[str], None] = 'f3c5a7e9b142'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('semester_teachers', sa.Column('homeroom_class_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'semester_teachers_homeroom_class_id_fkey',
        'semester_teachers',
        'classes',
        ['homeroom_class_id'],
        ['id'],
    )
    op.create_unique_constraint(
        'uq_semester_teacher_homeroom',
        'semester_teachers',
        ['schedule_version_id', 'homeroom_class_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_semester_teacher_homeroom', 'semester_teachers', type_='unique')
    op.drop_constraint(
        'semester_teachers_homeroom_class_id_fkey', 'semester_teachers', type_='foreignkey'
    )
    op.drop_column('semester_teachers', 'homeroom_class_id')
