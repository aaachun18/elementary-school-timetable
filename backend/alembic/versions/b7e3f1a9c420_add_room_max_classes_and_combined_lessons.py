"""add rooms.max_classes and combined lessons (共同排課)

- rooms.max_classes: how many classes may use the room at the same time
  (1-10, existing rooms 1 -- the old one-lesson-per-slot rule).
- combined_lessons / combined_lesson_members: lessons of several class
  subject requirements of one 排課紀錄 taught together (併班上課).

Revision ID: b7e3f1a9c420
Revises: a4d2c6e8f310
Create Date: 2026-10-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3f1a9c420'
down_revision: Union[str, Sequence[str], None] = 'a4d2c6e8f310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'rooms', sa.Column('max_classes', sa.Integer(), server_default='1', nullable=False)
    )
    op.create_check_constraint(
        'ck_rooms_max_classes_range', 'rooms', 'max_classes BETWEEN 1 AND 10'
    )

    op.create_table(
        'combined_lessons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schedule_version_id', sa.Integer(), nullable=False),
        sa.Column('merged_count', sa.Integer(), nullable=False),
        sa.Column('block_nos', sa.String(length=50), nullable=True),
        sa.Column('room_id', sa.Integer(), nullable=True),
        sa.Column('homeroom_class_id', sa.Integer(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint('merged_count >= 1', name='ck_combined_lessons_merged_count_positive'),
        sa.ForeignKeyConstraint(['schedule_version_id'], ['schedule_versions.id']),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id']),
        sa.ForeignKeyConstraint(['homeroom_class_id'], ['classes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'combined_lesson_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('combined_lesson_id', sa.Integer(), nullable=False),
        sa.Column('class_subject_requirement_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(['combined_lesson_id'], ['combined_lessons.id']),
        sa.ForeignKeyConstraint(
            ['class_subject_requirement_id'], ['class_subject_requirements.id']
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'class_subject_requirement_id', name='uq_combined_lesson_member_requirement'
        ),
        sa.UniqueConstraint(
            'combined_lesson_id', 'position', name='uq_combined_lesson_member_position'
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('combined_lesson_members')
    op.drop_table('combined_lessons')
    op.drop_constraint('ck_rooms_max_classes_range', 'rooms', type_='check')
    op.drop_column('rooms', 'max_classes')
