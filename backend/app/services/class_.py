from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.grade_class import Class
from app.schemas.class_ import ClassCreate, ClassUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_class(db: Session, class_data: ClassCreate) -> Class:
    class_obj = Class(
        grade_id=class_data.grade_id, name=class_data.name, is_active=True
    )
    db.add(class_obj)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(class_obj)
    return class_obj


def get_class(db: Session, class_id: int) -> Class | None:
    return db.get(Class, class_id)


def get_classes(db: Session, skip: int = 0, limit: int = 100) -> list[Class]:
    stmt = select(Class).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_class(db: Session, class_id: int, class_data: ClassUpdate) -> Class | None:
    class_obj = db.get(Class, class_id)
    if class_obj is None:
        return None

    for field, value in class_data.model_dump(exclude_unset=True).items():
        setattr(class_obj, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(class_obj)
    return class_obj


def delete_class(db: Session, class_id: int) -> bool:
    class_obj = db.get(Class, class_id)
    if class_obj is None:
        return False

    try:
        db.delete(class_obj)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Class {class_id} cannot be deleted: other records still "
            "reference it."
        ) from exc

    return True
