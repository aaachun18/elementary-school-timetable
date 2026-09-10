from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear
from app.schemas.academic_year import AcademicYearCreate, AcademicYearUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_academic_year(
    db: Session, academic_year_data: AcademicYearCreate
) -> AcademicYear:
    academic_year = AcademicYear(year=academic_year_data.year, is_active=True)
    db.add(academic_year)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(academic_year)
    return academic_year


def get_academic_year(db: Session, academic_year_id: int) -> AcademicYear | None:
    return db.get(AcademicYear, academic_year_id)


def get_academic_years(
    db: Session, skip: int = 0, limit: int = 100
) -> list[AcademicYear]:
    stmt = select(AcademicYear).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_academic_year(
    db: Session, academic_year_id: int, academic_year_data: AcademicYearUpdate
) -> AcademicYear | None:
    academic_year = db.get(AcademicYear, academic_year_id)
    if academic_year is None:
        return None

    for field, value in academic_year_data.model_dump(exclude_unset=True).items():
        setattr(academic_year, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(academic_year)
    return academic_year


def delete_academic_year(db: Session, academic_year_id: int) -> bool:
    academic_year = db.get(AcademicYear, academic_year_id)
    if academic_year is None:
        return False

    try:
        db.delete(academic_year)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"AcademicYear {academic_year_id} cannot be deleted: other "
            "records still reference it."
        ) from exc

    return True
