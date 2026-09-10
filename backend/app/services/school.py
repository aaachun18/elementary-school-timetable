from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.school import School
from app.schemas.school import SchoolCreate, SchoolUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_school(db: Session, school_data: SchoolCreate) -> School:
    school = School(name=school_data.name, is_active=True)
    db.add(school)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(school)
    return school


def get_school(db: Session, school_id: int) -> School | None:
    return db.get(School, school_id)


def get_schools(db: Session, skip: int = 0, limit: int = 100) -> list[School]:
    stmt = select(School).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_school(
    db: Session, school_id: int, school_data: SchoolUpdate
) -> School | None:
    school = db.get(School, school_id)
    if school is None:
        return None

    for field, value in school_data.model_dump(exclude_unset=True).items():
        setattr(school, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(school)
    return school


def delete_school(db: Session, school_id: int) -> bool:
    school = db.get(School, school_id)
    if school is None:
        return False

    try:
        db.delete(school)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"School {school_id} cannot be deleted: other records still "
            "reference it."
        ) from exc

    return True
