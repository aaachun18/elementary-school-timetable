from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.teacher import Teacher
from app.schemas.teacher import TeacherUpdate
from app.services.exceptions import raise_for_integrity_error
from app.services.school_scope import get_in_school, in_school

# Task 98: teachers are created and 停用 / 啟用 with their 一般老師 account
# (services/user.py); this module only reads them and renames one. Their
# per-semester settings are services/semester_settings.py.


def get_teacher(db: Session, teacher_id: int, *, school_id: int) -> Teacher | None:
    return get_in_school(db, Teacher, teacher_id, school_id)


def get_teachers(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[Teacher]:
    stmt = (
        select(Teacher)
        .where(in_school(Teacher, school_id))
        .order_by(Teacher.id)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def update_teacher(
    db: Session, teacher_id: int, teacher_data: TeacherUpdate, *, school_id: int
) -> Teacher | None:
    teacher = get_in_school(db, Teacher, teacher_id, school_id)
    if teacher is None:
        return None

    for field, value in teacher_data.model_dump(exclude_unset=True).items():
        setattr(teacher, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(teacher)
    return teacher
