"""add schedule_versions.wizard_furthest_step (開始排課 曾到達的最高步驟)

The furthest 開始排課 step a 排課紀錄 has reached, so the step row keeps
every step up to it clickable after a refresh or on another browser. Only
ever goes up. NULL for every existing record: the wizard then takes the step
it opens as the start.

Revision ID: e7b2c4d6f813
Revises: d4f6a8c0e215
Create Date: 2026-10-28 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b2c4d6f813'
down_revision: Union[str, Sequence[str], None] = 'd4f6a8c0e215'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'schedule_versions',
        sa.Column('wizard_furthest_step', sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        'ck_schedule_versions_wizard_furthest_step_non_negative',
        'schedule_versions',
        'wizard_furthest_step IS NULL OR wizard_furthest_step >= 0',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'ck_schedule_versions_wizard_furthest_step_non_negative',
        'schedule_versions',
        type_='check',
    )
    op.drop_column('schedule_versions', 'wizard_furthest_step')
