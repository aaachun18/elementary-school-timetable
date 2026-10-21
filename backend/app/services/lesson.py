from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule_version import ScheduleVersion
from app.models.time_slot import TimeSlot
from app.services.exceptions import raise_for_integrity_error
from app.services.schedule_version import (
    published_version_ids,
    raise_if_settings_locked,
)
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)


def get_lesson(
    db: Session, lesson_id: int, *, school_id: int, role: str | None = None
) -> Lesson | None:
    """Task 72: a TEACHER only sees a Lesson of a published record; any
    other one resolves to None (the router's existing 404), never a 403 --
    same stance as get_schedule_version(). `role=None` (the 教學組長 and
    every internal caller) sees every Lesson of the school."""
    lesson = get_in_school(db, Lesson, lesson_id, school_id)
    if lesson is None:
        return None
    if role == "TEACHER" and not _version_of(db, lesson).is_published:
        return None
    return lesson


def _version_of(db: Session, lesson: Lesson) -> ScheduleVersion:
    requirement = db.get(ClassSubjectRequirement, lesson.class_subject_requirement_id)
    assert requirement is not None  # FK
    schedule_version = db.get(ScheduleVersion, requirement.schedule_version_id)
    assert schedule_version is not None  # FK
    return schedule_version


def get_lessons(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    *,
    school_id: int,
    schedule_version_id: int | None = None,
    role: str | None = None,
) -> list[Lesson]:
    """Optional schedule_version_id filter -- Lesson has no record column
    of its own, so it goes through its ClassSubjectRequirement. An unknown
    record simply matches no rows. Ordered by id so skip/limit pages are
    stable. Task 72: a TEACHER only gets Lessons of published records
    (filtering by a hidden one is just empty)."""
    stmt = select(Lesson).where(in_school(Lesson, school_id))
    if schedule_version_id is not None or role == "TEACHER":
        stmt = stmt.join(
            ClassSubjectRequirement,
            Lesson.class_subject_requirement_id == ClassSubjectRequirement.id,
        )
    if schedule_version_id is not None:
        stmt = stmt.where(ClassSubjectRequirement.schedule_version_id == schedule_version_id)
    if role == "TEACHER":
        stmt = stmt.where(
            ClassSubjectRequirement.schedule_version_id.in_(published_version_ids())
        )
    stmt = stmt.order_by(Lesson.id).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def fix_lesson_time_slot(
    db: Session, lesson_id: int, time_slot_id: int | None, *, school_id: int
) -> Lesson | None:
    """Sets (or, with time_slot_id=None, clears) this Lesson's
    fixed_time_slot_id. Returns None if the Lesson doesn't exist (caller ->
    404). An invalid time_slot_id surfaces as a normal ForeignKeyViolation
    -> InvalidReferenceError -> 422, the same pattern every other
    create/update in this codebase already uses -- no need to pre-check
    existence by hand. (Task 98: a time slot of another school is refused
    the same way, by ensure_references_in_school().) v3: a fixed slot is
    a setting -- only a 尚未排課 record's lessons change (409 otherwise).
    """
    lesson = get_in_school(db, Lesson, lesson_id, school_id)
    if lesson is None:
        return None
    ensure_references_in_school(db, school_id, [(TimeSlot, time_slot_id)])
    raise_if_settings_locked(_version_of(db, lesson))

    lesson.fixed_time_slot_id = time_slot_id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(lesson)
    return lesson
