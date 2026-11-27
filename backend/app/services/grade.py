from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.grade_class import Grade
from app.services.school_scope import get_in_school, in_school

# Read only: a school's grades are built with the school
# (services/school.py) and fixed by its type.


def get_grade(db: Session, grade_id: int, *, school_id: int) -> Grade | None:
    return get_in_school(db, Grade, grade_id, school_id)


def get_grades(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[Grade]:
    stmt = (
        select(Grade)
        .where(in_school(Grade, school_id))
        .order_by(Grade.level)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
