from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.grade_class import Grade
from app.schemas.grade import GradeCreate, GradeUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.school_scope import get_in_school, in_school
from app.services.semester_settings import delete_settings_of_grade


def create_grade(db: Session, grade_data: GradeCreate, *, school_id: int) -> Grade:
    grade = Grade(school_id=school_id, name=grade_data.name, level=grade_data.level)
    db.add(grade)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(grade)
    return grade


def get_grade(db: Session, grade_id: int, *, school_id: int) -> Grade | None:
    return get_in_school(db, Grade, grade_id, school_id)


def get_grades(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[Grade]:
    stmt = select(Grade).where(in_school(Grade, school_id)).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_grade(
    db: Session, grade_id: int, grade_data: GradeUpdate, *, school_id: int
) -> Grade | None:
    grade = get_in_school(db, Grade, grade_id, school_id)
    if grade is None:
        return None

    for field, value in grade_data.model_dump(exclude_unset=True).items():
        setattr(grade, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(grade)
    return grade


def delete_grade(db: Session, grade_id: int, *, school_id: int) -> bool:
    grade = get_in_school(db, Grade, grade_id, school_id)
    if grade is None:
        return False

    try:
        # Task 98: its semesters' open slots are owned by it.
        delete_settings_of_grade(db, grade_id)
        db.delete(grade)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Grade {grade_id} cannot be deleted: other records still "
            "reference it."
        ) from exc

    return True
