from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.grade_class import Grade
from app.schemas.grade import GradeCreate, GradeUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_grade(db: Session, grade_data: GradeCreate) -> Grade:
    grade = Grade(name=grade_data.name, level=grade_data.level)
    db.add(grade)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(grade)
    return grade


def get_grade(db: Session, grade_id: int) -> Grade | None:
    return db.get(Grade, grade_id)


def get_grades(db: Session, skip: int = 0, limit: int = 100) -> list[Grade]:
    stmt = select(Grade).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_grade(
    db: Session, grade_id: int, grade_data: GradeUpdate
) -> Grade | None:
    grade = db.get(Grade, grade_id)
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


def delete_grade(db: Session, grade_id: int) -> bool:
    grade = db.get(Grade, grade_id)
    if grade is None:
        return False

    try:
        db.delete(grade)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Grade {grade_id} cannot be deleted: other records still "
            "reference it."
        ) from exc

    return True
