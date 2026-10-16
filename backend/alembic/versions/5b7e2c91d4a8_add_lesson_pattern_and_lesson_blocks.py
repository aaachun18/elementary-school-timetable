"""add lesson_pattern to requirements and block fields to lessons

Task 87: a requirement can split its weekly_periods into blocks of
consecutive lessons (class_subject_requirements.lesson_pattern, e.g.
"2+1"); each lesson records its block (lessons.block_no / block_seq).
All three are nullable -- existing rows stay "no pattern" and behave
exactly as before. consecutive_limit is left in place (deprecated, unused).

Revision ID: 5b7e2c91d4a8
Revises: a64c0f1e2b7d
Create Date: 2026-10-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b7e2c91d4a8'
down_revision: Union[str, Sequence[str], None] = 'a64c0f1e2b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BLOCK_FIELDS_CHECK_NAME = 'ck_lessons_block_fields_together'


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'class_subject_requirements',
        sa.Column('lesson_pattern', sa.String(length=20), nullable=True),
    )
    op.add_column('lessons', sa.Column('block_no', sa.Integer(), nullable=True))
    op.add_column('lessons', sa.Column('block_seq', sa.Integer(), nullable=True))
    op.create_check_constraint(
        BLOCK_FIELDS_CHECK_NAME,
        'lessons',
        '(block_no IS NULL) = (block_seq IS NULL)',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(BLOCK_FIELDS_CHECK_NAME, 'lessons', type_='check')
    op.drop_column('lessons', 'block_seq')
    op.drop_column('lessons', 'block_no')
    op.drop_column('class_subject_requirements', 'lesson_pattern')
