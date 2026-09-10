from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherAvailability, TeacherSubject
from app.models.time_slot import TimeSlot
from app.schemas.teacher import TeacherCreate, TeacherUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)

# --- Standard CRUD (same pattern as School / batch 1) ---


def create_teacher(db: Session, teacher_data: TeacherCreate) -> Teacher:
    teacher = Teacher(
        name=teacher_data.name,
        is_active=True,
        min_weekly_periods=teacher_data.min_weekly_periods,
        max_weekly_periods=teacher_data.max_weekly_periods,
    )
    db.add(teacher)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(teacher)
    return teacher


def get_teacher(db: Session, teacher_id: int) -> Teacher | None:
    return db.get(Teacher, teacher_id)


def get_teachers(db: Session, skip: int = 0, limit: int = 100) -> list[Teacher]:
    stmt = select(Teacher).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_teacher(
    db: Session, teacher_id: int, teacher_data: TeacherUpdate
) -> Teacher | None:
    teacher = db.get(Teacher, teacher_id)
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


def delete_teacher(db: Session, teacher_id: int) -> bool:
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        return False

    try:
        db.delete(teacher)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Teacher {teacher_id} cannot be deleted: other records still "
            "reference it."
        ) from exc

    return True


# --- Semantic sub-resource: teaching qualifications (TeacherSubject, H5) ---


def add_teacher_subject(
    db: Session, teacher_id: int, subject_id: int
) -> TeacherSubject:
    teacher_subject = TeacherSubject(teacher_id=teacher_id, subject_id=subject_id)
    db.add(teacher_subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(teacher_subject)
    return teacher_subject


def get_teacher_subjects(db: Session, teacher_id: int) -> list[Subject] | None:
    """Returns None if the teacher itself doesn't exist (caller should 404),
    or the (possibly empty) list of qualified subjects otherwise."""
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        return None
    return list(teacher.qualified_subjects)


def remove_teacher_subject(db: Session, teacher_id: int, subject_id: int) -> bool:
    stmt = select(TeacherSubject).where(
        TeacherSubject.teacher_id == teacher_id,
        TeacherSubject.subject_id == subject_id,
    )
    teacher_subject = db.scalars(stmt).first()
    if teacher_subject is None:
        return False

    db.delete(teacher_subject)
    db.commit()
    return True


# --- Semantic sub-resource: unavailable time slots (TeacherAvailability, H4) ---


def add_teacher_availability(
    db: Session, teacher_id: int, time_slot_id: int
) -> TeacherAvailability:
    teacher_availability = TeacherAvailability(
        teacher_id=teacher_id, time_slot_id=time_slot_id
    )
    db.add(teacher_availability)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(teacher_availability)
    return teacher_availability


def get_teacher_unavailable_slots(
    db: Session, teacher_id: int
) -> list[TimeSlot] | None:
    """Returns None if the teacher itself doesn't exist (caller should 404),
    or the (possibly empty) list of unavailable time slots otherwise."""
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        return None
    return list(teacher.unavailable_slots)


def remove_teacher_availability(
    db: Session, teacher_id: int, time_slot_id: int
) -> bool:
    stmt = select(TeacherAvailability).where(
        TeacherAvailability.teacher_id == teacher_id,
        TeacherAvailability.time_slot_id == time_slot_id,
    )
    teacher_availability = db.scalars(stmt).first()
    if teacher_availability is None:
        return False

    db.delete(teacher_availability)
    db.commit()
    return True
