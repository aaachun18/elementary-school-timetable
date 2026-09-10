from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.subject import Subject
from app.schemas.subject import SubjectCreate, SubjectUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_subject(db: Session, subject_data: SubjectCreate) -> Subject:
    subject = Subject(name=subject_data.name, is_active=True)
    db.add(subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(subject)
    return subject


def get_subject(db: Session, subject_id: int) -> Subject | None:
    return db.get(Subject, subject_id)


def get_subjects(db: Session, skip: int = 0, limit: int = 100) -> list[Subject]:
    stmt = select(Subject).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_subject(
    db: Session, subject_id: int, subject_data: SubjectUpdate
) -> Subject | None:
    subject = db.get(Subject, subject_id)
    if subject is None:
        return None

    for field, value in subject_data.model_dump(exclude_unset=True).items():
        setattr(subject, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(subject)
    return subject


def delete_subject(db: Session, subject_id: int) -> bool:
    subject = db.get(Subject, subject_id)
    if subject is None:
        return False

    try:
        db.delete(subject)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Subject {subject_id} cannot be deleted: other records still "
            "reference it."
        ) from exc

    return True
