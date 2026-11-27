"""scope root data by school

Task 98: teachers, subjects, rooms, academic_years, grades and time_slots
each belong to one school (school_id NOT NULL). Every other scheduling
table reaches its school through these (semester -> academic year, class
-> grade, requirement -> semester, ...), so it needs no column of its own.

The three formerly global unique values become unique per school:
subjects.name, academic_years.year, grades.level.

Existing rows are assigned to the first school (by id), or to a newly
created "預設學校" if there is none.

Revision ID: 9e2b6a4c8d13
Revises: 7c4d1e9a2f60
Create Date: 2026-10-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e2b6a4c8d13'
down_revision: Union[str, Sequence[str], None] = '7c4d1e9a2f60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCOPED_TABLES = ('teachers', 'subjects', 'rooms', 'academic_years', 'grades', 'time_slots')
DEFAULT_SCHOOL_NAME = '預設學校'

# (table, old global unique constraint, its column, new per-school constraint)
PER_SCHOOL_UNIQUES = (
    ('subjects', 'subjects_name_key', 'name', 'uq_subjects_school_name'),
    ('academic_years', 'academic_years_year_key', 'year', 'uq_academic_years_school_year'),
    ('grades', 'grades_level_key', 'level', 'uq_grades_school_level'),
)


def _fk_name(table: str) -> str:
    return f'fk_{table}_school_id_schools'


def _school_for_existing_rows(connection: sa.engine.Connection) -> int | None:
    """The school existing rows go to, or None when no table has rows."""
    has_rows = any(
        connection.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM {table})'))
        for table in SCOPED_TABLES
    )
    if not has_rows:
        return None
    school_id = connection.scalar(sa.text('SELECT min(id) FROM schools'))
    if school_id is None:
        school_id = connection.scalar(
            sa.text(
                'INSERT INTO schools (name, is_active) VALUES (:name, true) RETURNING id'
            ),
            {'name': DEFAULT_SCHOOL_NAME},
        )
    return school_id


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    school_id = _school_for_existing_rows(connection)

    for table in SCOPED_TABLES:
        op.add_column(table, sa.Column('school_id', sa.Integer(), nullable=True))
        if school_id is not None:
            connection.execute(
                sa.text(f'UPDATE {table} SET school_id = :school_id'),
                {'school_id': school_id},
            )
        op.alter_column(table, 'school_id', nullable=False)
        op.create_foreign_key(_fk_name(table), table, 'schools', ['school_id'], ['id'])

    for table, old_name, column, new_name in PER_SCHOOL_UNIQUES:
        op.drop_constraint(old_name, table, type_='unique')
        op.create_unique_constraint(new_name, table, ['school_id', column])


def downgrade() -> None:
    """Downgrade schema. Fails if two schools share a subject name, an
    academic year or a grade level -- they cannot be global again."""
    for table, old_name, column, new_name in PER_SCHOOL_UNIQUES:
        op.drop_constraint(new_name, table, type_='unique')
        op.create_unique_constraint(old_name, table, [column])

    for table in SCOPED_TABLES:
        op.drop_constraint(_fk_name(table), table, type_='foreignkey')
        op.drop_column(table, 'school_id')
