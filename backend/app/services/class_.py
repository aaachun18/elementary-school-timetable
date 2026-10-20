from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.grade_class import Class, Grade
from app.models.room import Room
from app.schemas.class_ import ClassCreate, ClassUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)


def create_class(db: Session, class_data: ClassCreate, *, school_id: int) -> Class:
    ensure_references_in_school(
        db,
        school_id,
        [(Grade, class_data.grade_id), (Room, class_data.homeroom_room_id)],
    )
    class_obj = Class(
        grade_id=class_data.grade_id,
        name=class_data.name,
        is_active=True,
        homeroom_room_id=class_data.homeroom_room_id,
    )
    db.add(class_obj)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(class_obj)
    return class_obj


def get_class(db: Session, class_id: int, *, school_id: int) -> Class | None:
    return get_in_school(db, Class, class_id, school_id)


def get_classes(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[Class]:
    stmt = select(Class).where(in_school(Class, school_id)).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_class(
    db: Session, class_id: int, class_data: ClassUpdate, *, school_id: int
) -> Class | None:
    class_obj = get_in_school(db, Class, class_id, school_id)
    if class_obj is None:
        return None

    changes = class_data.model_dump(exclude_unset=True)
    ensure_references_in_school(
        db,
        school_id,
        [(Grade, changes.get("grade_id")), (Room, changes.get("homeroom_room_id"))],
    )
    for field, value in changes.items():
        setattr(class_obj, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(class_obj)
    return class_obj


def delete_class(db: Session, class_id: int, *, school_id: int) -> bool:
    class_obj = get_in_school(db, Class, class_id, school_id)
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
