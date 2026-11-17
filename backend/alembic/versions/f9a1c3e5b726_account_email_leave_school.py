"""帳號改版：無所屬一般老師、教師離校、教學組長有教師資料、移除身分證字號

- users: a TEACHER account may now have no school (無所屬學校, after 離校);
  ADMIN still never has one, COORDINATOR always has one.
- teachers.has_left: the teacher row stays in the old school after 離校 (old
  timetables keep showing the name) but is out of scheduling. One account
  has at most one row that has not left (partial unique index), so going
  back to the old school can bring its row back.
- teachers.national_id (身分證字號) is dropped.
- Every existing COORDINATOR gets a Teacher row (教學組長 can be scheduled).

Revision ID: f9a1c3e5b726
Revises: e7b2c4d6f813
Create Date: 2026-11-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9a1c3e5b726'
down_revision: Union[str, Sequence[str], None] = 'e7b2c4d6f813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_SCHOOL_CHECK = (
    "(role = 'ADMIN' AND school_id IS NULL)"
    " OR (role = 'COORDINATOR' AND school_id IS NOT NULL)"
    " OR role = 'TEACHER'"
)
OLD_SCHOOL_CHECK = "(role = 'ADMIN') = (school_id IS NULL)"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('ck_users_school_matches_role', 'users', type_='check')
    op.create_check_constraint('ck_users_school_matches_role', 'users', NEW_SCHOOL_CHECK)

    op.add_column(
        'teachers',
        sa.Column('has_left', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_constraint('uq_teachers_user_id', 'teachers', type_='unique')
    op.create_index(
        'uq_teachers_user_id_current',
        'teachers',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text('has_left = false'),
    )

    op.drop_constraint('uq_teachers_school_national_id', 'teachers', type_='unique')
    op.drop_column('teachers', 'national_id')

    # 教學組長 now take part in scheduling: give each one its Teacher row
    # (same 0-0 starting range as an account-created teacher).
    op.execute(
        """
        INSERT INTO teachers
            (school_id, name, is_active, min_weekly_periods, max_weekly_periods,
             user_id, has_left, created_at, updated_at)
        SELECT u.school_id, u.username, u.is_active, 0, 0, u.id, false, now(), now()
        FROM users u
        WHERE u.role = 'COORDINATOR'
          AND NOT EXISTS (SELECT 1 FROM teachers t WHERE t.user_id = u.id)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # The old CHECK has no 無所屬 TEACHER: such accounts are deactivated and
    # put back in the school of their latest teacher row.
    op.execute(
        """
        UPDATE users u SET school_id = t.school_id, is_active = false
        FROM (
            SELECT DISTINCT ON (user_id) user_id, school_id
            FROM teachers WHERE user_id IS NOT NULL ORDER BY user_id, id DESC
        ) t
        WHERE u.role = 'TEACHER' AND u.school_id IS NULL AND t.user_id = u.id
        """
    )
    op.drop_constraint('ck_users_school_matches_role', 'users', type_='check')
    op.create_check_constraint('ck_users_school_matches_role', 'users', OLD_SCHOOL_CHECK)

    # Rows of teachers who left lose their account link, so the old
    # one-row-per-account constraint holds again.
    op.execute("UPDATE teachers SET user_id = NULL WHERE has_left")
    op.drop_index('uq_teachers_user_id_current', table_name='teachers')
    op.create_unique_constraint('uq_teachers_user_id', 'teachers', ['user_id'])
    op.drop_column('teachers', 'has_left')

    op.add_column('teachers', sa.Column('national_id', sa.String(length=10), nullable=True))
    op.create_unique_constraint(
        'uq_teachers_school_national_id', 'teachers', ['school_id', 'national_id']
    )
