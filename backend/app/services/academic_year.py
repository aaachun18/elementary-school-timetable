from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear
from app.schemas.academic_year import AcademicYearCreate, AcademicYearUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.school_scope import get_in_school, in_school


def create_academic_year(
    db: Session,
    academic_year_data: AcademicYearCreate,
    *,
    school_id: int,
) -> AcademicYear:
    academic_year = AcademicYear(
        school_id=school_id, year=academic_year_data.year, is_active=True
    )
    db.add(academic_year)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(academic_year)
    return academic_year


def get_academic_year(
    db: Session,
    academic_year_id: int,
    *,
    school_id: int,
) -> AcademicYear | None:
    return get_in_school(db, AcademicYear, academic_year_id, school_id)


def get_academic_years(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[AcademicYear]:
    stmt = select(
        AcademicYear
    ).where(in_school(AcademicYear, school_id)).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_academic_year(
    db: Session, academic_year_id: int, academic_year_data: AcademicYearUpdate, *, school_id: int
) -> AcademicYear | None:
    academic_year = get_in_school(db, AcademicYear, academic_year_id, school_id)
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


def delete_academic_year(db: Session, academic_year_id: int, *, school_id: int) -> bool:
    academic_year = get_in_school(db, AcademicYear, academic_year_id, school_id)
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
