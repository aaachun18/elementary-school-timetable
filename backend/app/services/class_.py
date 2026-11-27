from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.grade_class import Class, Grade
from app.schemas.class_ import ClassBatchCreate, ClassCreate
from app.services.deactivation import class_record_count
from app.services.delete_guidance import class_delete_steps
from app.services.exceptions import (
    ClassInUseError,
    DependentRecordsExistError,
    SchoolStructureViolationError,
    raise_for_integrity_error,
)
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)
from app.services.school_structure import ClassNameStyle, class_name_options

INVALID_CLASS_NAME_MESSAGE = "班級名稱必須是該年級與名稱類型提供的選項"
BATCH_TOO_MANY_MESSAGE = "這個年級的此名稱類型最多只能再新增 {available} 班"

# A class is only created, deactivated / reactivated and deleted (學校資料 >
# 班級); its grade and name never change.


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


def unused_class_names(db: Session, grade: Grade, name_style: ClassNameStyle) -> list[str]:
    """The style's names (in order) no class of the grade has yet."""
    used = set(db.scalars(select(Class.name).where(Class.grade_id == grade.id)).all())
    return [name for name in class_name_options(grade.level, name_style) if name not in used]


def create_classes_batch(
    db: Session, batch: ClassBatchCreate, *, school_id: int
) -> list[Class]:
    """批次新增: the first `count` unused names of the style, all or none
    (one transaction). More than the style has left -> 422."""
    ensure_references_in_school(db, school_id, [(Grade, batch.grade_id)])
    grade = db.get(Grade, batch.grade_id)
    assert grade is not None  # checked just above
    names = unused_class_names(db, grade, batch.name_style)
    if batch.count > len(names):
        raise SchoolStructureViolationError(BATCH_TOO_MANY_MESSAGE.format(available=len(names)))

    classes = [
        Class(grade_id=grade.id, name=name, name_style=batch.name_style.value)
        for name in names[: batch.count]
    ]
    db.add_all(classes)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    for class_obj in classes:
        db.refresh(class_obj)
    return classes


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


def set_class_active(
    db: Session, class_id: int, is_active: bool, *, school_id: int
) -> Class | None:
    """停用 / 啟用. Nothing else changes: the class's requirements in old
    records stay; new scheduling just leaves an inactive class out."""
    class_obj = get_in_school(db, Class, class_id, school_id)
    if class_obj is None:
        return None
    class_obj.is_active = is_active
    db.commit()
    db.refresh(class_obj)
    return class_obj


def delete_class(db: Session, class_id: int, *, school_id: int) -> bool:
    """A class no 排課紀錄 uses is deleted; one in use -> ClassInUseError
    (409 CLASS_IN_USE with the record count), to be deactivated instead."""
    class_obj = get_in_school(db, Class, class_id, school_id)
    if class_obj is None:
        return False

    record_count = class_record_count(db, class_id)
    if record_count > 0:
        raise ClassInUseError(
            f"Class {class_id} is used by {record_count} schedule record(s).",
            record_count,
            class_delete_steps(db, class_id),
        )

    try:
        db.delete(class_obj)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Class {class_id} cannot be deleted: other records still "
            "reference it.",
            class_delete_steps(db, class_id),
        ) from exc

    return True
