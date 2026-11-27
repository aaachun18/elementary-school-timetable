"""add teachers.national_id (身分證字號 for 同名同姓 teachers)

Nullable: only a teacher sharing a name with another teacher of the school
needs one. Unique per school (several NULLs allowed).

Revision ID: c2e4a6f8b310
Revises: b7e3f1a9c420
Create Date: 2026-10-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2e4a6f8b310'
down_revision: Union[str, Sequence[str], None] = 'b7e3f1a9c420'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('teachers', sa.Column('national_id', sa.String(length=10), nullable=True))
    op.create_unique_constraint(
        'uq_teachers_school_national_id',
        'teachers',
        ['school_id', 'national_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_teachers_school_national_id', 'teachers', type_='unique')
    op.drop_column('teachers', 'national_id')
