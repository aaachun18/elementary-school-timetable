"""add ARCHIVED schedule version status and one PUBLISHED per semester

Revision ID: a64c0f1e2b7d
Revises: f8314700cad8
Create Date: 2026-10-13 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a64c0f1e2b7d'
down_revision: Union[str, Sequence[str], None] = 'f8314700cad8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS_CHECK_NAME = 'ck_schedule_versions_status_valid'
ONE_PUBLISHED_INDEX_NAME = 'uq_schedule_versions_one_published_per_semester'


def upgrade() -> None:
    """Upgrade schema.

    status is a plain VARCHAR(20) guarded by a CHECK constraint (not a
    PostgreSQL enum type), so adding ARCHIVED is just replacing that CHECK.
    """
    op.drop_constraint(STATUS_CHECK_NAME, 'schedule_versions', type_='check')
    op.create_check_constraint(
        STATUS_CHECK_NAME,
        'schedule_versions',
        "status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')",
    )

    # Before this revision, a semester could have several PUBLISHED versions.
    # The unique index below allows only one, so existing data is resolved
    # first by this rule: in each semester, the PUBLISHED version with the
    # highest version_number stays PUBLISHED, and every other PUBLISHED
    # version of that semester becomes ARCHIVED (kept, still locked,
    # publishable again later). version_number is unique per semester
    # (uq_schedule_version_semester_number), so "highest" is never a tie.
    op.execute(
        """
        UPDATE schedule_versions AS older
        SET status = 'ARCHIVED'
        WHERE older.status = 'PUBLISHED'
          AND EXISTS (
              SELECT 1
              FROM schedule_versions AS newer
              WHERE newer.semester_id = older.semester_id
                AND newer.status = 'PUBLISHED'
                AND newer.version_number > older.version_number
          )
        """
    )

    op.create_index(
        ONE_PUBLISHED_INDEX_NAME,
        'schedule_versions',
        ['semester_id'],
        unique=True,
        postgresql_where=sa.text("status = 'PUBLISHED'"),
    )


def downgrade() -> None:
    """Downgrade schema.

    The previous CHECK only allows DRAFT/PUBLISHED, so every ARCHIVED row
    must become one of them first. They become PUBLISHED, not DRAFT: an
    ARCHIVED version WAS published, and before this revision several
    PUBLISHED versions per semester were allowed, so this restores exactly
    the old meaning. Turning them into DRAFT would instead silently unlock
    historical timetables for editing and deletion.
    """
    op.drop_index(ONE_PUBLISHED_INDEX_NAME, table_name='schedule_versions')
    op.execute(
        "UPDATE schedule_versions SET status = 'PUBLISHED' WHERE status = 'ARCHIVED'"
    )
    op.drop_constraint(STATUS_CHECK_NAME, 'schedule_versions', type_='check')
    op.create_check_constraint(
        STATUS_CHECK_NAME,
        'schedule_versions',
        "status IN ('DRAFT', 'PUBLISHED')",
    )
