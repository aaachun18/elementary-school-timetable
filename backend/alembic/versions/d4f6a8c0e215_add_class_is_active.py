"""add classes.is_active (班級停用)

A class used by a 排課紀錄 can't be deleted; it is deactivated instead, so
new scheduling leaves it out while old records keep it. Every existing
class starts active (server default true).

Revision ID: d4f6a8c0e215
Revises: c2e4a6f8b310
Create Date: 2026-10-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f6a8c0e215'
down_revision: Union[str, Sequence[str], None] = 'c2e4a6f8b310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'classes',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('classes', 'is_active')
