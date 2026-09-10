from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import Semester
from app.schemas.semester import SemesterCreate, SemesterUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_semester(db: Session, semester_data: SemesterCreate) -> Semester:
    semester = Semester(
        academic_year_id=semester_data.academic_year_id,
        number=semester_data.number,
        is_active=True,
    )
    db.add(semester)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(semester)
    return semester


def get_semester(db: Session, semester_id: int) -> Semester | None:
    return db.get(Semester, semester_id)


def get_semesters(db: Session, skip: int = 0, limit: int = 100) -> list[Semester]:
    stmt = select(Semester).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_semester(
    db: Session, semester_id: int, semester_data: SemesterUpdate
) -> Semester | None:
    semester = db.get(Semester, semester_id)
    if semester is None:
        return None

    for field, value in semester_data.model_dump(exclude_unset=True).items():
        setattr(semester, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(semester)
    return semester


def delete_semester(db: Session, semester_id: int) -> bool:
    semester = db.get(Semester, semester_id)
    if semester is None:
        return False

    try:
        db.delete(semester)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Semester {semester_id} cannot be deleted: other records "
            "still reference it."
        ) from exc

    return True
