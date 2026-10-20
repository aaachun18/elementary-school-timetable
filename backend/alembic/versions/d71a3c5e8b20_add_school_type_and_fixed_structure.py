"""add school type, fixed grades / time slots and grade subject requirements

- schools.school_type (國小 / 國中 / 高中); existing schools become 國小.
- grades.level may be 1-12 (高中 10-12, shown as 一到三年級).
- classes: homeroom_room_id and is_active are dropped (未指定教室 = 原班上課,
  no room at all; every class is active); name_style is added and
  (grade_id, name) becomes unique.
- rooms.capacity and time_slots.start_time / end_time are dropped.
- time_slots: (school_id, weekday, period) becomes unique. Every existing
  school gets the missing slots of its 國小 grid (Monday-Friday, periods
  0-9; 0 / 5 / 9 not schedulable) and its missing 國小 grades 1-6, the way
  a newly created school is built.
- grade_subject_requirements: a school's weekly periods per grade and
  subject.

Revision ID: d71a3c5e8b20
Revises: c8a35d1f6e27
Create Date: 2026-10-20 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd71a3c5e8b20'
down_revision: Union[str, Sequence[str], None] = 'c8a35d1f6e27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ELEMENTARY_LEVELS = (1, 2, 3, 4, 5, 6)
ELEMENTARY_GRADE_NAMES = ('一年級', '二年級', '三年級', '四年級', '五年級', '六年級')
ELEMENTARY_LAST_PERIOD = 9
FIXED_LABELS = {0: '早自習', 5: '午休', ELEMENTARY_LAST_PERIOD: '放學'}


def _complete_existing_schools(connection: sa.engine.Connection) -> None:
    school_ids = connection.scalars(sa.text('SELECT id FROM schools')).all()
    for school_id in school_ids:
        for weekday in range(1, 6):
            for period in range(0, ELEMENTARY_LAST_PERIOD + 1):
                connection.execute(
                    sa.text(
                        'INSERT INTO time_slots (school_id, weekday, period, '
                        'is_teaching_period, label) '
                        'SELECT :school_id, :weekday, :period, :teaching, :label '
                        'WHERE NOT EXISTS (SELECT 1 FROM time_slots WHERE '
                        'school_id = :school_id AND weekday = :weekday AND period = :period)'
                    ),
                    {
                        'school_id': school_id,
                        'weekday': weekday,
                        'period': period,
                        'teaching': period not in FIXED_LABELS,
                        'label': FIXED_LABELS.get(period),
                    },
                )
        for level, name in zip(ELEMENTARY_LEVELS, ELEMENTARY_GRADE_NAMES):
            connection.execute(
                sa.text(
                    'INSERT INTO grades (school_id, name, level) '
                    'SELECT :school_id, :name, :level '
                    'WHERE NOT EXISTS (SELECT 1 FROM grades WHERE '
                    'school_id = :school_id AND level = :level)'
                ),
                {'school_id': school_id, 'name': name, 'level': level},
            )


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'schools',
        sa.Column(
            'school_type', sa.String(length=20), nullable=False, server_default='ELEMENTARY'
        ),
    )
    op.create_check_constraint(
        'ck_schools_school_type_valid',
        'schools',
        "school_type IN ('ELEMENTARY', 'JUNIOR_HIGH', 'SENIOR_HIGH')",
    )

    op.drop_constraint('ck_grades_level_valid', 'grades', type_='check')
    op.create_check_constraint('ck_grades_level_valid', 'grades', 'level BETWEEN 1 AND 12')

    op.drop_constraint('classes_homeroom_room_id_fkey', 'classes', type_='foreignkey')
    op.drop_column('classes', 'homeroom_room_id')
    op.drop_column('classes', 'is_active')
    op.add_column(
        'classes',
        sa.Column('name_style', sa.String(length=20), nullable=False, server_default='NUMBER'),
    )
    op.create_check_constraint(
        'ck_classes_name_style_valid',
        'classes',
        "name_style IN ('NUMBER', 'HEAVENLY_STEM', 'VIRTUE')",
    )
    # Older free-text names may repeat within a grade: keep the first, and
    # suffix the others with their id so the new unique constraint holds.
    op.execute(
        "UPDATE classes SET name = name || '-' || id WHERE id NOT IN "
        '(SELECT min(id) FROM classes GROUP BY grade_id, name)'
    )
    op.create_unique_constraint('uq_classes_grade_name', 'classes', ['grade_id', 'name'])

    op.drop_column('rooms', 'capacity')

    op.drop_column('time_slots', 'start_time')
    op.drop_column('time_slots', 'end_time')
    op.create_unique_constraint(
        'uq_time_slots_school_weekday_period', 'time_slots', ['school_id', 'weekday', 'period']
    )

    _complete_existing_schools(op.get_bind())

    op.create_table(
        'grade_subject_requirements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('grade_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('weekly_periods', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            'weekly_periods BETWEEN 1 AND 6',
            name='ck_grade_subject_requirements_weekly_periods_valid',
        ),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.id']),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('grade_id', 'subject_id', name='uq_grade_subject_requirement'),
    )


def downgrade() -> None:
    """Downgrade schema. The slots and grades added for existing schools,
    the class name suffixes and the dropped columns' old values are not
    restored: classes come back active with no homeroom, rooms with no
    capacity, time slots with no clock times."""
    op.drop_table('grade_subject_requirements')

    op.drop_constraint('uq_time_slots_school_weekday_period', 'time_slots', type_='unique')
    op.add_column('time_slots', sa.Column('end_time', sa.Time(), nullable=True))
    op.add_column('time_slots', sa.Column('start_time', sa.Time(), nullable=True))

    op.add_column('rooms', sa.Column('capacity', sa.Integer(), nullable=True))

    op.drop_constraint('uq_classes_grade_name', 'classes', type_='unique')
    op.drop_constraint('ck_classes_name_style_valid', 'classes', type_='check')
    op.drop_column('classes', 'name_style')
    op.add_column(
        'classes',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('classes', 'is_active', server_default=None)
    op.add_column('classes', sa.Column('homeroom_room_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'classes_homeroom_room_id_fkey', 'classes', 'rooms', ['homeroom_room_id'], ['id']
    )

    # Levels 10-12 (高中) don't fit the old 1-9 range.
    op.execute('DELETE FROM grades WHERE level > 9 AND id NOT IN (SELECT grade_id FROM classes)')
    op.drop_constraint('ck_grades_level_valid', 'grades', type_='check')
    op.create_check_constraint('ck_grades_level_valid', 'grades', 'level BETWEEN 1 AND 9')

    op.drop_constraint('ck_schools_school_type_valid', 'schools', type_='check')
    op.drop_column('schools', 'school_type')
