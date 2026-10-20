from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.grade_class import Class, Grade
from app.schemas.class_ import ClassCreate
from app.services.exceptions import (
    DependentRecordsExistError,
    SchoolStructureViolationError,
    raise_for_integrity_error,
)
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)
from app.services.school_structure import class_name_options

INVALID_CLASS_NAME_MESSAGE = "班級名稱必須是該年級與名稱類型提供的選項"

# A class is only created and deleted (學校資料 > 班級), never edited.


def create_class(db: Session, class_data: ClassCreate, *, school_id: int) -> Class:
    """The name must be one of the grade's options in the chosen style
    (一年甲班 ...); the same name twice in a grade -> 409 (unique)."""
    ensure_references_in_school(db, school_id, [(Grade, class_data.grade_id)])
    grade = db.get(Grade, class_data.grade_id)
    assert grade is not None  # checked just above
    if class_data.name not in class_name_options(grade.level, class_data.name_style):
        raise SchoolStructureViolationError(INVALID_CLASS_NAME_MESSAGE)

    class_obj = Class(
        grade_id=class_data.grade_id,
        name=class_data.name,
        name_style=class_data.name_style.value,
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
    db: Session,
    skip: int = 0,
    limit: int = 100,
    *,
    school_id: int,
    grade_id: int | None = None,
) -> list[Class]:
    stmt = select(Class).where(in_school(Class, school_id))
    if grade_id is not None:
        stmt = stmt.where(Class.grade_id == grade_id)
    stmt = stmt.order_by(Class.grade_id, Class.id).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


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
