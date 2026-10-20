"""add semester scheduling settings, grade level range, required room

Task 98 (scheduling wizard):
- semester_teachers: which teachers take part in a semester's scheduling,
  with that semester's weekly periods range;
- semester_teacher_unavailabilities: their unavailable slots that semester;
- semester_grade_time_slots: the slots each grade may use that semester;
- grades.level limited to 1-9 (國小 1-6, 國中 7-9);
- class_subject_requirements.required_room_id: the one special room.

Existing grades with a level outside 1-9 are renumbered, per school and in
level order, to the lowest free levels 1-9; a school with more than nine
grades cannot be migrated and stops the upgrade with a clear error.

Revision ID: b4f71c2e9a05
Revises: 9e2b6a4c8d13
Create Date: 2026-10-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f71c2e9a05'
down_revision: Union[str, Sequence[str], None] = '9e2b6a4c8d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MIN_LEVEL = 1
MAX_LEVEL = 9
GRADE_LEVEL_CHECK_NAME = 'ck_grades_level_valid'
REQUIRED_ROOM_FK_NAME = 'fk_class_subject_requirements_required_room_id_rooms'


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    ]


def _renumber_out_of_range_levels(connection: sa.engine.Connection) -> None:
    rows = connection.execute(
        sa.text('SELECT id, school_id, level FROM grades ORDER BY school_id, level, id')
    ).all()
    used: dict[int, set[int]] = {}
    for _, school_id, level in rows:
        if MIN_LEVEL <= level <= MAX_LEVEL:
            used.setdefault(school_id, set()).add(level)
    for grade_id, school_id, level in rows:
        if MIN_LEVEL <= level <= MAX_LEVEL:
            continue
        taken = used.setdefault(school_id, set())
        free = [n for n in range(MIN_LEVEL, MAX_LEVEL + 1) if n not in taken]
        if not free:
            raise RuntimeError(
                f'School {school_id} has more than {MAX_LEVEL} grades; grade '
                f'{grade_id} (level {level}) has no free level 1-{MAX_LEVEL}. '
                'Remove or merge grades before upgrading.'
            )
        connection.execute(
            sa.text('UPDATE grades SET level = :level WHERE id = :id'),
            {'level': free[0], 'id': grade_id},
        )
        taken.add(free[0])


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'semester_teachers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('semester_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('min_weekly_periods', sa.Integer(), nullable=False),
        sa.Column('max_weekly_periods', sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            'min_weekly_periods >= 0', name='ck_semester_teachers_min_not_negative'
        ),
        sa.CheckConstraint(
            'min_weekly_periods <= max_weekly_periods',
            name='ck_semester_teachers_periods_range',
        ),
        sa.ForeignKeyConstraint(['semester_id'], ['semesters.id']),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('semester_id', 'teacher_id', name='uq_semester_teacher'),
    )
    op.create_table(
        'semester_teacher_unavailabilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('semester_teacher_id', sa.Integer(), nullable=False),
        sa.Column('time_slot_id', sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(['semester_teacher_id'], ['semester_teachers.id']),
        sa.ForeignKeyConstraint(['time_slot_id'], ['time_slots.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'semester_teacher_id', 'time_slot_id', name='uq_semester_teacher_unavailability'
        ),
    )
    op.create_table(
        'semester_grade_time_slots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('semester_id', sa.Integer(), nullable=False),
        sa.Column('grade_id', sa.Integer(), nullable=False),
        sa.Column('time_slot_id', sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(['semester_id'], ['semesters.id']),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.id']),
        sa.ForeignKeyConstraint(['time_slot_id'], ['time_slots.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'semester_id', 'grade_id', 'time_slot_id', name='uq_semester_grade_time_slot'
        ),
    )

    _renumber_out_of_range_levels(op.get_bind())
    op.create_check_constraint(
        GRADE_LEVEL_CHECK_NAME, 'grades', f'level BETWEEN {MIN_LEVEL} AND {MAX_LEVEL}'
    )

    op.add_column(
        'class_subject_requirements',
        sa.Column('required_room_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        REQUIRED_ROOM_FK_NAME,
        'class_subject_requirements',
        'rooms',
        ['required_room_id'],
        ['id'],
    )


def downgrade() -> None:
    """Downgrade schema. Renumbered grade levels are not restored."""
    op.drop_constraint(REQUIRED_ROOM_FK_NAME, 'class_subject_requirements', type_='foreignkey')
    op.drop_column('class_subject_requirements', 'required_room_id')
    op.drop_constraint(GRADE_LEVEL_CHECK_NAME, 'grades', type_='check')
    op.drop_table('semester_grade_time_slots')
    op.drop_table('semester_teacher_unavailabilities')
    op.drop_table('semester_teachers')
