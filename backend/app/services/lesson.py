from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.services.exceptions import raise_for_integrity_error
from app.services.schedule_version import (
    published_semester_ids,
    semester_has_published_version,
)


def get_lesson(
    db: Session, lesson_id: int, *, role: str | None = None
) -> Lesson | None:
    """Task 72: a TEACHER only sees a Lesson whose semester currently has a
    PUBLISHED version; any other one resolves to None (the router's
    existing 404), never a 403 -- same stance as get_schedule_version().
    `role=None` (ADMIN and every internal caller) sees every Lesson."""
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        return None
    if role == "TEACHER":
        requirement = db.get(ClassSubjectRequirement, lesson.class_subject_requirement_id)
        if requirement is None or not semester_has_published_version(
            db, requirement.semester_id
        ):
            return None
    return lesson


def get_lessons(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    *,
    semester_id: int | None = None,
    role: str | None = None,
) -> list[Lesson]:
    """Task 66: optional semester_id filter -- Lesson has no semester column
    of its own, so it goes through its ClassSubjectRequirement. An unknown
    semester simply matches no rows. Ordered by id so skip/limit pages are
    stable. Task 72: a TEACHER only gets Lessons of semesters that currently
    have a PUBLISHED version (filtering by a hidden semester is just empty)."""
    stmt = select(Lesson)
    if semester_id is not None or role == "TEACHER":
        stmt = stmt.join(
            ClassSubjectRequirement,
            Lesson.class_subject_requirement_id == ClassSubjectRequirement.id,
        )
    if semester_id is not None:
        stmt = stmt.where(ClassSubjectRequirement.semester_id == semester_id)
    if role == "TEACHER":
        stmt = stmt.where(
            ClassSubjectRequirement.semester_id.in_(published_semester_ids())
        )
    stmt = stmt.order_by(Lesson.id).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def fix_lesson_time_slot(
    db: Session, lesson_id: int, time_slot_id: int | None
) -> Lesson | None:
    """Sets (or, with time_slot_id=None, clears) this Lesson's
    fixed_time_slot_id. Returns None if the Lesson doesn't exist (caller ->
    404). An invalid time_slot_id surfaces as a normal ForeignKeyViolation
    -> InvalidReferenceError -> 422, the same pattern every other
    create/update in this codebase already uses -- no need to pre-check
    existence by hand.
    """
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        return None

    lesson.fixed_time_slot_id = time_slot_id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(lesson)
    return lesson
