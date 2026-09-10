from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import Lesson


def get_lesson(db: Session, lesson_id: int) -> Lesson | None:
    return db.get(Lesson, lesson_id)


def get_lessons(db: Session, skip: int = 0, limit: int = 100) -> list[Lesson]:
    stmt = select(Lesson).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())
