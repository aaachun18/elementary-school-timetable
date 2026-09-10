from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.time_slot import TimeSlot
from app.schemas.time_slot import TimeSlotCreate, TimeSlotUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_time_slot(db: Session, time_slot_data: TimeSlotCreate) -> TimeSlot:
    time_slot = TimeSlot(**time_slot_data.model_dump())
    db.add(time_slot)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(time_slot)
    return time_slot


def get_time_slot(db: Session, time_slot_id: int) -> TimeSlot | None:
    return db.get(TimeSlot, time_slot_id)


def get_time_slots(db: Session, skip: int = 0, limit: int = 100) -> list[TimeSlot]:
    stmt = select(TimeSlot).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_time_slot(
    db: Session, time_slot_id: int, time_slot_data: TimeSlotUpdate
) -> TimeSlot | None:
    time_slot = db.get(TimeSlot, time_slot_id)
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


def delete_time_slot(db: Session, time_slot_id: int) -> bool:
    time_slot = db.get(TimeSlot, time_slot_id)
    if time_slot is None:
        return False

    try:
        db.delete(time_slot)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"TimeSlot {time_slot_id} cannot be deleted: other records "
            "still reference it."
        ) from exc

    return True
