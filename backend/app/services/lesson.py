from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lesson import Lesson
from app.services.exceptions import raise_for_integrity_error


def get_lesson(db: Session, lesson_id: int) -> Lesson | None:
    return db.get(Lesson, lesson_id)


def get_lessons(db: Session, skip: int = 0, limit: int = 100) -> list[Lesson]:
    stmt = select(Lesson).offset(skip).limit(limit)
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
