from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.teacher import TeacherAvailability
from app.models.time_slot import TimeSlot
from app.schemas.time_slot import TimeSlotCreate, TimeSlotUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.semester_settings import delete_settings_of_time_slot
from app.services.school_scope import get_in_school, in_school


def create_time_slot(
    db: Session,
    time_slot_data: TimeSlotCreate,
    *,
    school_id: int,
) -> TimeSlot:
    time_slot = TimeSlot(**time_slot_data.model_dump(), school_id=school_id)
    db.add(time_slot)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(time_slot)
    return time_slot


def get_time_slot(db: Session, time_slot_id: int, *, school_id: int) -> TimeSlot | None:
    return get_in_school(db, TimeSlot, time_slot_id, school_id)


def get_time_slots(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[TimeSlot]:
    stmt = select(
        TimeSlot
    ).where(in_school(TimeSlot, school_id)).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_time_slot(
    db: Session, time_slot_id: int, time_slot_data: TimeSlotUpdate, *, school_id: int
) -> TimeSlot | None:
    time_slot = get_in_school(db, TimeSlot, time_slot_id, school_id)
    if time_slot is None:
        return None

    for field, value in time_slot_data.model_dump(exclude_unset=True).items():
        setattr(time_slot, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(time_slot)
    return time_slot


def delete_time_slot(db: Session, time_slot_id: int, *, school_id: int) -> bool:
    time_slot = get_in_school(db, TimeSlot, time_slot_id, school_id)
    if time_slot is None:
        return False

    # Task 50: TeacherAvailability is a join entity between Teacher and
    # TimeSlot with no independent meaning of its own ("this teacher is
    # unavailable at this slot" stops meaning anything once the slot
    # itself is gone), and its FK to time_slots.id has no ON DELETE
    # CASCADE, so without this ANY time slot a teacher ever marked
    # themselves unavailable for could never be deleted at all.
    #
    # Lesson.fixed_time_slot_id and Schedule.time_slot_id are deliberately
    # left alone -- unlike TeacherAvailability, a manually-fixed Lesson or
    # an actual placed Schedule entry is real, meaningful data that must
    # keep blocking the delete (silently un-fixing/un-placing it would
    # destroy that data, not just an association that no longer means
    # anything).
    #
    # Staged on `db` but not committed yet -- if the final commit() fails
    # (one of those two real references), the rollback() undoes the whole
    # transaction, including these deletes, so no teacher's unavailable
    # slots are lost on a failed delete attempt.
    unavailabilities = db.scalars(
        select(TeacherAvailability).where(
            TeacherAvailability.time_slot_id == time_slot_id
        )
    ).all()
    for unavailability in unavailabilities:
        db.delete(unavailability)
    # Task 98: the same for the semesters' own settings.
    delete_settings_of_time_slot(db, time_slot_id)

    db.delete(time_slot)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"TimeSlot {time_slot_id} cannot be deleted: other records "
            "still reference it."
        ) from exc

    return True
