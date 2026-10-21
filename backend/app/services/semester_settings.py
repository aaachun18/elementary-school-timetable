"""Task 98: a 排課紀錄's scheduling settings -- the wizard's 教師設定 (which
teachers take part, their weekly periods range and unavailable slots) and
年級與可排節次 (the slots each grade is open for). Both are replaced as a
whole by the wizard rather than edited row by row.

v3: every record owns its own settings (schedule_version_id), and only a
尚未排課 record's change (SettingsLockedError otherwise) -- a record with a
timetable keeps the settings it was made under.
"""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.grade_class import Grade
from app.models.schedule_version import ScheduleVersion
from app.models.semester_grade_time_slot import SemesterGradeTimeSlot
from app.models.semester_teacher import SemesterTeacher, SemesterTeacherUnavailability
from app.models.teacher import Teacher
from app.models.time_slot import TimeSlot
from app.schemas.semester_settings import (
    GradeTimeSlotsRead,
    SemesterTeacherRead,
    SemesterTeachersUpdate,
)
from app.services.exceptions import (
    InactiveTeacherAssignmentError,
    SchoolStructureViolationError,
    raise_for_integrity_error,
)
from app.services.grade_levels import SlotPosition, default_open_slot_ids
from app.services.schedule_version import get_schedule_version, raise_if_settings_locked
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)

NOT_SCHEDULABLE_SLOT_MESSAGE = "不可排課的時段不能設為年級可排節次"

# --- teachers (教師設定) ---


def _read_semester_teachers(db: Session, version_id: int) -> list[SemesterTeacherRead]:
    rows = db.execute(
        select(SemesterTeacher, Teacher.name)
        .join(Teacher, SemesterTeacher.teacher_id == Teacher.id)
        .where(SemesterTeacher.schedule_version_id == version_id)
        .order_by(SemesterTeacher.teacher_id)
    ).all()
    unavailable: dict[int, list[int]] = {}
    for semester_teacher_id, time_slot_id in db.execute(
        select(
            SemesterTeacherUnavailability.semester_teacher_id,
            SemesterTeacherUnavailability.time_slot_id,
        )
        .join(SemesterTeacher)
        .where(SemesterTeacher.schedule_version_id == version_id)
        .order_by(SemesterTeacherUnavailability.time_slot_id)
    ).all():
        unavailable.setdefault(semester_teacher_id, []).append(time_slot_id)
    return [
        SemesterTeacherRead(
            teacher_id=semester_teacher.teacher_id,
            teacher_name=name,
            min_weekly_periods=semester_teacher.min_weekly_periods,
            max_weekly_periods=semester_teacher.max_weekly_periods,
            unavailable_time_slot_ids=unavailable.get(semester_teacher.id, []),
        )
        for semester_teacher, name in rows
    ]


def get_semester_teachers(
    db: Session, version_id: int, *, school_id: int, role: str | None = None
) -> list[SemesterTeacherRead] | None:
    """None if the record doesn't exist in the school -- or, for a TEACHER,
    isn't published (caller -> 404)."""
    if get_schedule_version(db, version_id, school_id=school_id, role=role) is None:
        return None
    return _read_semester_teachers(db, version_id)


def _delete_semester_teachers(db: Session, version_id: int) -> None:
    semester_teacher_ids = select(SemesterTeacher.id).where(
        SemesterTeacher.schedule_version_id == version_id
    )
    db.execute(
        delete(SemesterTeacherUnavailability).where(
            SemesterTeacherUnavailability.semester_teacher_id.in_(semester_teacher_ids)
        )
    )
    db.execute(delete(SemesterTeacher).where(SemesterTeacher.schedule_version_id == version_id))


def replace_semester_teachers(
    db: Session, version_id: int, data: SemesterTeachersUpdate, *, school_id: int
) -> list[SemesterTeacherRead] | None:
    """The record's teachers become exactly `data.teachers`. Every teacher
    and time slot must be of the school (else 422), and every teacher
    active -- only 啟用 accounts take part (else 409). None if the record
    doesn't exist in the school; a record that is not 尚未排課 -> 409. One
    transaction."""
    schedule_version = get_in_school(db, ScheduleVersion, version_id, school_id)
    if schedule_version is None:
        return None
    raise_if_settings_locked(schedule_version)
    ensure_references_in_school(
        db,
        school_id,
        [(Teacher, entry.teacher_id) for entry in data.teachers]
        + [
            (TimeSlot, time_slot_id)
            for entry in data.teachers
            for time_slot_id in entry.unavailable_time_slot_ids
        ],
    )
    for entry in data.teachers:
        teacher = db.get(Teacher, entry.teacher_id)
        assert teacher is not None  # checked just above
        if not teacher.is_active:
            raise InactiveTeacherAssignmentError(
                f"Teacher {entry.teacher_id} is inactive and cannot take part."
            )

    try:
        _delete_semester_teachers(db, version_id)
        for entry in data.teachers:
            semester_teacher = SemesterTeacher(
                schedule_version_id=version_id,
                teacher_id=entry.teacher_id,
                min_weekly_periods=entry.min_weekly_periods,
                max_weekly_periods=entry.max_weekly_periods,
            )
            db.add(semester_teacher)
            db.flush()
            db.add_all(
                SemesterTeacherUnavailability(
                    semester_teacher_id=semester_teacher.id, time_slot_id=time_slot_id
                )
                for time_slot_id in sorted(set(entry.unavailable_time_slot_ids))
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    return _read_semester_teachers(db, version_id)


# --- grades' open time slots (年級與可排節次) ---


def _read_grade_time_slots(db: Session, version_id: int) -> list[GradeTimeSlotsRead]:
    slots_by_grade: dict[int, list[int]] = {}
    for grade_id, time_slot_id in db.execute(
        select(SemesterGradeTimeSlot.grade_id, SemesterGradeTimeSlot.time_slot_id)
        .where(SemesterGradeTimeSlot.schedule_version_id == version_id)
        .order_by(SemesterGradeTimeSlot.grade_id, SemesterGradeTimeSlot.time_slot_id)
    ).all():
        slots_by_grade.setdefault(grade_id, []).append(time_slot_id)
    return [
        GradeTimeSlotsRead(grade_id=grade_id, time_slot_ids=time_slot_ids)
        for grade_id, time_slot_ids in slots_by_grade.items()
    ]


def get_grade_time_slots(
    db: Session, version_id: int, *, school_id: int, role: str | None = None
) -> list[GradeTimeSlotsRead] | None:
    """Every grade that has its open slots set in the record. A grade left
    out has none set -- it is then not restricted at all (see
    services/scheduler.py). None if the record doesn't exist (or, for a
    TEACHER, isn't published)."""
    if get_schedule_version(db, version_id, school_id=school_id, role=role) is None:
        return None
    return _read_grade_time_slots(db, version_id)


def replace_grade_time_slots(
    db: Session,
    version_id: int,
    grade_id: int,
    time_slot_ids: list[int],
    *,
    school_id: int,
) -> GradeTimeSlotsRead | None:
    """The grade's open slots in the record become exactly `time_slot_ids`
    (at least one -- the schema refuses an empty list). None if the record
    or the grade doesn't exist in the school; a record that is not 尚未排課
    -> 409; a time slot of another school, or one the school marked not
    schedulable (學校資料 > 時段) -> 422."""
    schedule_version = get_in_school(db, ScheduleVersion, version_id, school_id)
    if schedule_version is None or get_in_school(db, Grade, grade_id, school_id) is None:
        return None
    raise_if_settings_locked(schedule_version)
    ensure_references_in_school(
        db, school_id, [(TimeSlot, time_slot_id) for time_slot_id in time_slot_ids]
    )
    closed = db.scalars(
        select(TimeSlot.id).where(
            TimeSlot.id.in_(time_slot_ids), TimeSlot.is_teaching_period.is_(False)
        )
    ).first()
    if closed is not None:
        raise SchoolStructureViolationError(NOT_SCHEDULABLE_SLOT_MESSAGE)
    try:
        db.execute(
            delete(SemesterGradeTimeSlot).where(
                SemesterGradeTimeSlot.schedule_version_id == version_id,
                SemesterGradeTimeSlot.grade_id == grade_id,
            )
        )
        db.add_all(
            SemesterGradeTimeSlot(
                schedule_version_id=version_id, grade_id=grade_id, time_slot_id=time_slot_id
            )
            for time_slot_id in time_slot_ids
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    return GradeTimeSlotsRead(grade_id=grade_id, time_slot_ids=sorted(time_slot_ids))


def default_grade_time_slots(db: Session, grade_id: int, *, school_id: int) -> list[int] | None:
    """The school's time slots the grade is open for by default (its
    band's period ranges, teaching periods only -- see
    services/grade_levels.py), in weekday / period order. None if the grade
    doesn't exist in the school."""
    grade = get_in_school(db, Grade, grade_id, school_id)
    if grade is None:
        return None
    slots = db.scalars(
        select(TimeSlot)
        .where(in_school(TimeSlot, school_id))
        .order_by(TimeSlot.weekday, TimeSlot.period, TimeSlot.id)
    ).all()
    return default_open_slot_ids(
        grade.level,
        [
            SlotPosition(slot.id, slot.weekday, slot.period, slot.is_teaching_period)
            for slot in slots
        ],
    )
