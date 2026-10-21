"""v3: every 排課紀錄 owns its own settings; new record statuses and numbers

schedule_versions (排課紀錄):
- status: DRAFT / PUBLISHED / ARCHIVED become NOT_SCHEDULED (尚未排課),
  AUTO (自動排課), MANUAL (手動排課), COPIED (複製自編號 x) or EDITING (a
  manual edit's hidden working copy). Publishing is a separate flag,
  is_published -- still at most one per semester. Existing records become
  AUTO when they have a timetable (or were published / archived), else
  NOT_SCHEDULED; the published one stays published.
- school_id (the record's school) and version_number: one 編號 sequence per
  school (existing records renumbered oldest first); NULL only for EDITING.
- copied_from_number, editing_source_id and note (備註) are added.

class_subject_requirements, semester_teachers, semester_grade_time_slots:
semester_id is replaced by schedule_version_id -- the settings belong to one
record, not to the semester. Each semester's existing settings go to its
oldest record; every other record of the semester gets its own copy (with
copies of the lessons, and its Schedule rows moved onto them). A semester
with settings but no record gets a 尚未排課 record to keep them.

Downgrade is lossy: working copies are dropped; per semester only the
oldest record's settings are kept (other records' Schedule rows are moved
back onto those lessons by class, subject and sequence number, and dropped
where none matches); the published record becomes PUBLISHED, every other
DRAFT.

Revision ID: f3c5a7e9b142
Revises: e1a7c3b9d250
Create Date: 2026-10-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c5a7e9b142'
down_revision: Union[str, Sequence[str], None] = 'e1a7c3b9d250'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SETTINGS_TABLES = ('class_subject_requirements', 'semester_teachers', 'semester_grade_time_slots')


def _rows(connection: sa.engine.Connection, sql: str, **params: object) -> list[sa.Row]:
    return list(connection.execute(sa.text(sql), params).all())


def _insert_returning_id(connection: sa.engine.Connection, sql: str, **params: object) -> int:
    return connection.execute(sa.text(sql + ' RETURNING id'), params).scalar_one()


# --- upgrade ---


def _clone_settings(
    connection: sa.engine.Connection, source_version_id: int, target_version_id: int
) -> dict[int, int]:
    """Copies of the source record's settings for the target (semester_id
    still filled: the column goes only once every row has its record).
    Returns {old lesson id: new lesson id}."""
    lesson_map: dict[int, int] = {}
    for requirement in _rows(
        connection,
        'SELECT * FROM class_subject_requirements WHERE schedule_version_id = :v ORDER BY id',
        v=source_version_id,
    ):
        new_requirement_id = _insert_returning_id(
            connection,
            'INSERT INTO class_subject_requirements (schedule_version_id, semester_id, '
            'class_id, subject_id, weekly_periods, required_teacher_id, required_room_type, '
            'consecutive_limit, lesson_pattern, required_room_id) VALUES (:v, :semester_id, '
            ':class_id, :subject_id, :weekly_periods, :required_teacher_id, '
            ':required_room_type, :consecutive_limit, :lesson_pattern, :required_room_id)',
            v=target_version_id,
            semester_id=requirement.semester_id,
            class_id=requirement.class_id,
            subject_id=requirement.subject_id,
            weekly_periods=requirement.weekly_periods,
            required_teacher_id=requirement.required_teacher_id,
            required_room_type=requirement.required_room_type,
            consecutive_limit=requirement.consecutive_limit,
            lesson_pattern=requirement.lesson_pattern,
            required_room_id=requirement.required_room_id,
        )
        for lesson in _rows(
            connection,
            'SELECT * FROM lessons WHERE class_subject_requirement_id = :r ORDER BY id',
            r=requirement.id,
        ):
            lesson_map[lesson.id] = _insert_returning_id(
                connection,
                'INSERT INTO lessons (class_subject_requirement_id, sequence_number, '
                'fixed_time_slot_id, block_no, block_seq) VALUES (:r, :sequence_number, '
                ':fixed_time_slot_id, :block_no, :block_seq)',
                r=new_requirement_id,
                sequence_number=lesson.sequence_number,
                fixed_time_slot_id=lesson.fixed_time_slot_id,
                block_no=lesson.block_no,
                block_seq=lesson.block_seq,
            )
    for semester_teacher in _rows(
        connection,
        'SELECT * FROM semester_teachers WHERE schedule_version_id = :v ORDER BY id',
        v=source_version_id,
    ):
        new_id = _insert_returning_id(
            connection,
            'INSERT INTO semester_teachers (schedule_version_id, semester_id, teacher_id, '
            'min_weekly_periods, max_weekly_periods) VALUES (:v, :semester_id, :teacher_id, '
            ':min, :max)',
            v=target_version_id,
            semester_id=semester_teacher.semester_id,
            teacher_id=semester_teacher.teacher_id,
            min=semester_teacher.min_weekly_periods,
            max=semester_teacher.max_weekly_periods,
        )
        connection.execute(
            sa.text(
                'INSERT INTO semester_teacher_unavailabilities (semester_teacher_id, '
                'time_slot_id) SELECT :new_id, time_slot_id FROM '
                'semester_teacher_unavailabilities WHERE semester_teacher_id = :old_id'
            ),
            {'new_id': new_id, 'old_id': semester_teacher.id},
        )
    connection.execute(
        sa.text(
            'INSERT INTO semester_grade_time_slots (schedule_version_id, semester_id, '
            'grade_id, time_slot_id) SELECT :target, semester_id, grade_id, time_slot_id '
            'FROM semester_grade_time_slots WHERE schedule_version_id = :source'
        ),
        {'target': target_version_id, 'source': source_version_id},
    )
    return lesson_map


def _give_settings_to_records(connection: sa.engine.Connection) -> None:
    semester_ids = sorted(
        {
            row[0]
            for table in SETTINGS_TABLES
            for row in _rows(connection, f'SELECT DISTINCT semester_id FROM {table}')
        }
        | {row[0] for row in _rows(connection, 'SELECT DISTINCT semester_id FROM schedule_versions')}
    )
    for semester_id in semester_ids:
        version_ids = [
            row.id
            for row in _rows(
                connection,
                'SELECT id FROM schedule_versions WHERE semester_id = :s ORDER BY id',
                s=semester_id,
            )
        ]
        if not version_ids:
            school_id = connection.execute(
                sa.text(
                    'SELECT y.school_id FROM semesters s JOIN academic_years y '
                    'ON y.id = s.academic_year_id WHERE s.id = :s'
                ),
                {'s': semester_id},
            ).scalar_one()
            next_number = connection.execute(
                sa.text(
                    'SELECT COALESCE(MAX(version_number), 0) + 1 FROM schedule_versions '
                    'WHERE school_id = :school'
                ),
                {'school': school_id},
            ).scalar_one()
            version_ids = [
                _insert_returning_id(
                    connection,
                    'INSERT INTO schedule_versions (school_id, semester_id, version_number, '
                    "status, is_published) VALUES (:school, :s, :n, 'NOT_SCHEDULED', false)",
                    school=school_id,
                    s=semester_id,
                    n=next_number,
                )
            ]
        first, *others = version_ids
        for table in SETTINGS_TABLES:
            connection.execute(
                sa.text(f'UPDATE {table} SET schedule_version_id = :v WHERE semester_id = :s'),
                {'v': first, 's': semester_id},
            )
        for version_id in others:
            lesson_map = _clone_settings(connection, first, version_id)
            for schedule in _rows(
                connection,
                'SELECT id, lesson_id FROM schedules WHERE schedule_version_id = :v',
                v=version_id,
            ):
                if schedule.lesson_id in lesson_map:
                    connection.execute(
                        sa.text('UPDATE schedules SET lesson_id = :l WHERE id = :id'),
                        {'l': lesson_map[schedule.lesson_id], 'id': schedule.id},
                    )


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    # schedule_versions: the new columns, filled from the old ones.
    op.drop_index(
        'uq_schedule_versions_one_published_per_semester', table_name='schedule_versions'
    )
    op.drop_constraint('uq_schedule_version_semester_number', 'schedule_versions', type_='unique')
    op.drop_constraint('ck_schedule_versions_status_valid', 'schedule_versions', type_='check')
    op.add_column('schedule_versions', sa.Column('school_id', sa.Integer(), sa.ForeignKey('schools.id'), nullable=True))
    op.add_column(
        'schedule_versions',
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('schedule_versions', sa.Column('copied_from_number', sa.Integer(), nullable=True))
    op.add_column(
        'schedule_versions',
        sa.Column(
            'editing_source_id', sa.Integer(), sa.ForeignKey('schedule_versions.id'), nullable=True
        ),
    )
    op.add_column('schedule_versions', sa.Column('note', sa.String(length=200), nullable=True))
    op.alter_column('schedule_versions', 'version_number', nullable=True)
    connection.execute(
        sa.text(
            'UPDATE schedule_versions v SET school_id = y.school_id FROM semesters s '
            'JOIN academic_years y ON y.id = s.academic_year_id WHERE s.id = v.semester_id'
        )
    )
    connection.execute(
        sa.text(
            "UPDATE schedule_versions SET is_published = (status = 'PUBLISHED'), status = "
            "CASE WHEN status IN ('PUBLISHED', 'ARCHIVED') OR EXISTS (SELECT 1 FROM schedules "
            "WHERE schedule_version_id = schedule_versions.id) THEN 'AUTO' "
            "ELSE 'NOT_SCHEDULED' END"
        )
    )
    connection.execute(
        sa.text(
            'UPDATE schedule_versions v SET version_number = n.number FROM ('
            'SELECT id, ROW_NUMBER() OVER (PARTITION BY school_id ORDER BY created_at, id) '
            'AS number FROM schedule_versions) n WHERE n.id = v.id'
        )
    )

    # Settings: semester_id -> schedule_version_id.
    for table in SETTINGS_TABLES:
        op.add_column(
            table,
            sa.Column(
                'schedule_version_id',
                sa.Integer(),
                sa.ForeignKey('schedule_versions.id'),
                nullable=True,
            ),
        )
    # The old per-semester uniques would refuse a record's copy.
    op.drop_constraint('uq_class_subject_requirement', 'class_subject_requirements', type_='unique')
    op.drop_constraint('uq_semester_teacher', 'semester_teachers', type_='unique')
    op.drop_constraint('uq_semester_grade_time_slot', 'semester_grade_time_slots', type_='unique')
    _give_settings_to_records(connection)
    op.alter_column('schedule_versions', 'school_id', nullable=False)
    for table in SETTINGS_TABLES:
        op.alter_column(table, 'schedule_version_id', nullable=False)
    for table in SETTINGS_TABLES:
        op.drop_column(table, 'semester_id')
    op.create_unique_constraint(
        'uq_class_subject_requirement',
        'class_subject_requirements',
        ['schedule_version_id', 'class_id', 'subject_id'],
    )
    op.create_unique_constraint(
        'uq_semester_teacher', 'semester_teachers', ['schedule_version_id', 'teacher_id']
    )
    op.create_unique_constraint(
        'uq_semester_grade_time_slot',
        'semester_grade_time_slots',
        ['schedule_version_id', 'grade_id', 'time_slot_id'],
    )

    # schedule_versions: the new rules.
    op.create_check_constraint(
        'ck_schedule_versions_status_valid',
        'schedule_versions',
        "status IN ('NOT_SCHEDULED', 'AUTO', 'MANUAL', 'COPIED', 'EDITING')",
    )
    op.create_check_constraint(
        'ck_schedule_versions_number_unless_editing',
        'schedule_versions',
        "(status = 'EDITING') = (version_number IS NULL)",
    )
    op.create_check_constraint(
        'ck_schedule_versions_editing_source',
        'schedule_versions',
        "(status = 'EDITING') = (editing_source_id IS NOT NULL)",
    )
    op.create_check_constraint(
        'ck_schedule_versions_copied_from',
        'schedule_versions',
        "(status = 'COPIED') = (copied_from_number IS NOT NULL)",
    )
    op.create_check_constraint(
        'ck_schedule_versions_published_has_timetable',
        'schedule_versions',
        "NOT is_published OR status IN ('AUTO', 'MANUAL', 'COPIED')",
    )
    op.create_unique_constraint(
        'uq_schedule_versions_school_number', 'schedule_versions', ['school_id', 'version_number']
    )
    op.create_index(
        'uq_schedule_versions_one_published_per_semester',
        'schedule_versions',
        ['semester_id'],
        unique=True,
        postgresql_where=sa.text('is_published'),
    )


# --- downgrade ---


def _delete_version_contents(connection: sa.engine.Connection, version_id: int) -> None:
    for sql in (
        'DELETE FROM schedules WHERE schedule_version_id = :v',
        'DELETE FROM lessons WHERE class_subject_requirement_id IN '
        '(SELECT id FROM class_subject_requirements WHERE schedule_version_id = :v)',
        'DELETE FROM class_subject_requirements WHERE schedule_version_id = :v',
        'DELETE FROM semester_teacher_unavailabilities WHERE semester_teacher_id IN '
        '(SELECT id FROM semester_teachers WHERE schedule_version_id = :v)',
        'DELETE FROM semester_teachers WHERE schedule_version_id = :v',
        'DELETE FROM semester_grade_time_slots WHERE schedule_version_id = :v',
    ):
        connection.execute(sa.text(sql), {'v': version_id})


def _keep_one_settings_per_semester(connection: sa.engine.Connection) -> None:
    for (semester_id,) in _rows(connection, 'SELECT DISTINCT semester_id FROM schedule_versions'):
        first, *others = [
            row.id
            for row in _rows(
                connection,
                'SELECT id FROM schedule_versions WHERE semester_id = :s ORDER BY id',
                s=semester_id,
            )
        ]
        kept = {
            (row.class_id, row.subject_id, row.sequence_number): row.id
            for row in _rows(
                connection,
                'SELECT l.id, r.class_id, r.subject_id, l.sequence_number FROM lessons l '
                'JOIN class_subject_requirements r ON r.id = l.class_subject_requirement_id '
                'WHERE r.schedule_version_id = :v',
                v=first,
            )
        }
        for version_id in others:
            for row in _rows(
                connection,
                'SELECT s.id, r.class_id, r.subject_id, l.sequence_number FROM schedules s '
                'JOIN lessons l ON l.id = s.lesson_id JOIN class_subject_requirements r '
                'ON r.id = l.class_subject_requirement_id WHERE s.schedule_version_id = :v',
                v=version_id,
            ):
                key = (row.class_id, row.subject_id, row.sequence_number)
                if key in kept:
                    connection.execute(
                        sa.text('UPDATE schedules SET lesson_id = :l WHERE id = :id'),
                        {'l': kept[key], 'id': row.id},
                    )
                else:
                    connection.execute(sa.text('DELETE FROM schedules WHERE id = :id'), {'id': row.id})
            # Their own settings go; the moved Schedule rows stay.
            for sql in (
                'DELETE FROM lessons WHERE class_subject_requirement_id IN '
                '(SELECT id FROM class_subject_requirements WHERE schedule_version_id = :v)',
                'DELETE FROM class_subject_requirements WHERE schedule_version_id = :v',
                'DELETE FROM semester_teacher_unavailabilities WHERE semester_teacher_id IN '
                '(SELECT id FROM semester_teachers WHERE schedule_version_id = :v)',
                'DELETE FROM semester_teachers WHERE schedule_version_id = :v',
                'DELETE FROM semester_grade_time_slots WHERE schedule_version_id = :v',
            ):
                connection.execute(sa.text(sql), {'v': version_id})


def downgrade() -> None:
    """Downgrade schema (lossy -- see the module docstring)."""
    connection = op.get_bind()

    for (version_id,) in _rows(connection, "SELECT id FROM schedule_versions WHERE status = 'EDITING'"):
        _delete_version_contents(connection, version_id)
        connection.execute(sa.text('DELETE FROM schedule_versions WHERE id = :v'), {'v': version_id})
    _keep_one_settings_per_semester(connection)

    op.drop_index('uq_schedule_versions_one_published_per_semester', table_name='schedule_versions')
    op.drop_constraint('uq_schedule_versions_school_number', 'schedule_versions', type_='unique')
    for name in (
        'ck_schedule_versions_published_has_timetable',
        'ck_schedule_versions_copied_from',
        'ck_schedule_versions_editing_source',
        'ck_schedule_versions_number_unless_editing',
        'ck_schedule_versions_status_valid',
    ):
        op.drop_constraint(name, 'schedule_versions', type_='check')

    for table in SETTINGS_TABLES:
        op.add_column(
            table,
            sa.Column('semester_id', sa.Integer(), sa.ForeignKey('semesters.id'), nullable=True),
        )
        connection.execute(
            sa.text(
                f'UPDATE {table} t SET semester_id = v.semester_id FROM schedule_versions v '
                'WHERE v.id = t.schedule_version_id'
            )
        )
        op.alter_column(table, 'semester_id', nullable=False)
    op.drop_constraint('uq_class_subject_requirement', 'class_subject_requirements', type_='unique')
    op.drop_constraint('uq_semester_teacher', 'semester_teachers', type_='unique')
    op.drop_constraint('uq_semester_grade_time_slot', 'semester_grade_time_slots', type_='unique')
    for table in SETTINGS_TABLES:
        op.drop_column(table, 'schedule_version_id')
    op.create_unique_constraint(
        'uq_class_subject_requirement',
        'class_subject_requirements',
        ['semester_id', 'class_id', 'subject_id'],
    )
    op.create_unique_constraint('uq_semester_teacher', 'semester_teachers', ['semester_id', 'teacher_id'])
    op.create_unique_constraint(
        'uq_semester_grade_time_slot',
        'semester_grade_time_slots',
        ['semester_id', 'grade_id', 'time_slot_id'],
    )

    connection.execute(
        sa.text(
            "UPDATE schedule_versions SET status = CASE WHEN is_published THEN 'PUBLISHED' "
            "ELSE 'DRAFT' END"
        )
    )
    connection.execute(
        sa.text(
            'UPDATE schedule_versions v SET version_number = n.number FROM ('
            'SELECT id, ROW_NUMBER() OVER (PARTITION BY semester_id ORDER BY id) AS number '
            'FROM schedule_versions) n WHERE n.id = v.id'
        )
    )
    op.alter_column('schedule_versions', 'version_number', nullable=False)
    op.drop_column('schedule_versions', 'note')
    op.drop_column('schedule_versions', 'editing_source_id')
    op.drop_column('schedule_versions', 'copied_from_number')
    op.drop_column('schedule_versions', 'is_published')
    op.drop_column('schedule_versions', 'school_id')
    op.create_check_constraint(
        'ck_schedule_versions_status_valid',
        'schedule_versions',
        "status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')",
    )
    op.create_unique_constraint(
        'uq_schedule_version_semester_number', 'schedule_versions', ['semester_id', 'version_number']
    )
    op.create_index(
        'uq_schedule_versions_one_published_per_semester',
        'schedule_versions',
        ['semester_id'],
        unique=True,
        postgresql_where=sa.text("status = 'PUBLISHED'"),
    )
