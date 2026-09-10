from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.schemas.class_subject_requirement import (
    ClassSubjectRequirementCreate,
    ClassSubjectRequirementUpdate,
)
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_class_subject_requirement(
    db: Session, requirement_data: ClassSubjectRequirementCreate
) -> ClassSubjectRequirement:
    requirement = ClassSubjectRequirement(**requirement_data.model_dump())
    db.add(requirement)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(requirement)
    return requirement


def get_class_subject_requirement(
    db: Session, requirement_id: int
) -> ClassSubjectRequirement | None:
    return db.get(ClassSubjectRequirement, requirement_id)


def get_class_subject_requirements(
    db: Session, skip: int = 0, limit: int = 100
) -> list[ClassSubjectRequirement]:
    stmt = select(ClassSubjectRequirement).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_class_subject_requirement(
    db: Session,
    requirement_id: int,
    requirement_data: ClassSubjectRequirementUpdate,
) -> ClassSubjectRequirement | None:
    requirement = db.get(ClassSubjectRequirement, requirement_id)
    if requirement is None:
        return None

    for field, value in requirement_data.model_dump(exclude_unset=True).items():
        setattr(requirement, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(requirement)
    return requirement


def delete_class_subject_requirement(db: Session, requirement_id: int) -> bool:
    requirement = db.get(ClassSubjectRequirement, requirement_id)
    if requirement is None:
        return False

    try:
        db.delete(requirement)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"ClassSubjectRequirement {requirement_id} cannot be deleted: "
            "other records still reference it."
        ) from exc

    return True
