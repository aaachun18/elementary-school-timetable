"""Task 98: one semester's scheduling settings -- the wizard's steps 4-6
(which teachers take part, their weekly periods range and unavailable
slots) and step 8 (the slots each grade is open for). Both are replaced as
a whole by the wizard rather than edited row by row.

Not locked by a published version: the settings are shared by every
version of the semester (like its requirements), and a new DRAFT of a
published timetable must be able to change them. Re-checking a published
version afterwards judges it against the current settings.
"""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import Semester
from app.models.grade_class import Grade
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
    raise_for_integrity_error,
)
from app.services.grade_levels import SlotPosition, default_open_slot_ids
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)

# --- teachers (steps 4-6) ---


def _read_semester_teachers(db: Session, semester_id: int) -> list[SemesterTeacherRead]:
    rows = db.execute(
        select(SemesterTeacher, Teacher.name)
        .join(Teacher, SemesterTeacher.teacher_id == Teacher.id)
        .where(SemesterTeacher.semester_id == semester_id)
        .order_by(SemesterTeacher.teacher_id)
    ).all()
    unavailable: dict[int, list[int]] = {}
    for semester_teacher_id, time_slot_id in db.execute(
        select(
            SemesterTeacherUnavailability.semester_teacher_id,
            SemesterTeacherUnavailability.time_slot_id,
        )
        .join(SemesterTeacher)
        .where(SemesterTeacher.semester_id == semester_id)
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
    db: Session, semester_id: int, *, school_id: int
) -> list[SemesterTeacherRead] | None:
    """None if the semester doesn't exist in the school (caller -> 404)."""
    if get_in_school(db, Semester, semester_id, school_id) is None:
        return None
    return _read_semester_teachers(db, semester_id)


def _delete_semester_teachers(db: Session, semester_id: int) -> None:
    semester_teacher_ids = select(SemesterTeacher.id).where(
        SemesterTeacher.semester_id == semester_id
    )
    db.execute(
        delete(SemesterTeacherUnavailability).where(
            SemesterTeacherUnavailability.semester_teacher_id.in_(semester_teacher_ids)
        )
    )
    db.execute(delete(SemesterTeacher).where(SemesterTeacher.semester_id == semester_id))


def replace_semester_teachers(
    db: Session, semester_id: int, data: SemesterTeachersUpdate, *, school_id: int
) -> list[SemesterTeacherRead] | None:
    """The semester's teachers become exactly `data.teachers`. Every
    teacher and time slot must be of the school (else 422), and every
    teacher active -- only 啟用 accounts take part (else 409). None if the
    semester doesn't exist in the school. One transaction."""
    if get_in_school(db, Semester, semester_id, school_id) is None:
        return None
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
        _delete_semester_teachers(db, semester_id)
        for entry in data.teachers:
            semester_teacher = SemesterTeacher(
                semester_id=semester_id,
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
    return _read_semester_teachers(db, semester_id)


# --- grades' open time slots (step 8) ---


def _read_grade_time_slots(db: Session, semester_id: int) -> list[GradeTimeSlotsRead]:
    slots_by_grade: dict[int, list[int]] = {}
    for grade_id, time_slot_id in db.execute(
        select(SemesterGradeTimeSlot.grade_id, SemesterGradeTimeSlot.time_slot_id)
        .where(SemesterGradeTimeSlot.semester_id == semester_id)
        .order_by(SemesterGradeTimeSlot.grade_id, SemesterGradeTimeSlot.time_slot_id)
    ).all():
        slots_by_grade.setdefault(grade_id, []).append(time_slot_id)
    return [
        GradeTimeSlotsRead(grade_id=grade_id, time_slot_ids=time_slot_ids)
        for grade_id, time_slot_ids in slots_by_grade.items()
    ]


def get_grade_time_slots(
    db: Session, semester_id: int, *, school_id: int
) -> list[GradeTimeSlotsRead] | None:
    """Every grade that has its open slots set for the semester. A grade
    left out has none set -- it is then not restricted at all (see
    services/scheduler.py). None if the semester doesn't exist."""
    if get_in_school(db, Semester, semester_id, school_id) is None:
        return None
    return _read_grade_time_slots(db, semester_id)


def replace_grade_time_slots(
    db: Session,
    semester_id: int,
    grade_id: int,
    time_slot_ids: list[int],
    *,
    school_id: int,
) -> GradeTimeSlotsRead | None:
    """The grade's open slots for the semester become exactly
    `time_slot_ids` (at least one -- the schema refuses an empty list).
    None if the semester or the grade doesn't exist in the school; a time
    slot of another school -> 422."""
    if (
        get_in_school(db, Semester, semester_id, school_id) is None
        or get_in_school(db, Grade, grade_id, school_id) is None
    ):
        return None
    ensure_references_in_school(
        db, school_id, [(TimeSlot, time_slot_id) for time_slot_id in time_slot_ids]
    )
    try:
        db.execute(
            delete(SemesterGradeTimeSlot).where(
                SemesterGradeTimeSlot.semester_id == semester_id,
                SemesterGradeTimeSlot.grade_id == grade_id,
            )
        )
        db.add_all(
            SemesterGradeTimeSlot(
                semester_id=semester_id, grade_id=grade_id, time_slot_id=time_slot_id
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


# --- owned rows other deletes take with them ---


def delete_settings_of_semester(db: Session, semester_id: int) -> None:
    """Staged, not committed: a deleted semester's settings go with it."""
    _delete_semester_teachers(db, semester_id)
    db.execute(
        delete(SemesterGradeTimeSlot).where(SemesterGradeTimeSlot.semester_id == semester_id)
    )


def delete_settings_of_time_slot(db: Session, time_slot_id: int) -> None:
    """Staged, not committed: a deleted time slot stops being anyone's
    unavailable slot or any grade's open slot."""
    db.execute(
        delete(SemesterTeacherUnavailability).where(
            SemesterTeacherUnavailability.time_slot_id == time_slot_id
        )
    )
    db.execute(
        delete(SemesterGradeTimeSlot).where(SemesterGradeTimeSlot.time_slot_id == time_slot_id)
    )


def delete_settings_of_grade(db: Session, grade_id: int) -> None:
    """Staged, not committed: a deleted grade's open slots go with it."""
    db.execute(delete(SemesterGradeTimeSlot).where(SemesterGradeTimeSlot.grade_id == grade_id))
