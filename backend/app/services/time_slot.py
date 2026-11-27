from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.time_slot import TimeSlot
from app.schemas.time_slot import TimeSlotBulkUpdateItem, TimeSlotUpdate
from app.services.exceptions import InvalidReferenceError, raise_for_integrity_error
from app.services.school_scope import get_in_school, in_school

# A school's time slot grid is built with the school (services/school.py)
# and never grows or shrinks -- there is no create or delete here. Only a
# slot's label and whether it is schedulable change.


def get_time_slot(db: Session, time_slot_id: int, *, school_id: int) -> TimeSlot | None:
    return get_in_school(db, TimeSlot, time_slot_id, school_id)


def get_time_slots(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[TimeSlot]:
    stmt = (
        select(TimeSlot)
        .where(in_school(TimeSlot, school_id))
        .order_by(TimeSlot.weekday, TimeSlot.period)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def _apply(time_slot: TimeSlot, time_slot_data: TimeSlotUpdate) -> None:
    for field, value in time_slot_data.model_dump(exclude_unset=True).items():
        if field == "label" and isinstance(value, str):
            # An emptied label input means "no label".
            value = value.strip() or None
        setattr(time_slot, field, value)


def update_time_slot(
    db: Session, time_slot_id: int, time_slot_data: TimeSlotUpdate, *, school_id: int
) -> TimeSlot | None:
    time_slot = get_in_school(db, TimeSlot, time_slot_id, school_id)
    if time_slot is None:
        return None

    _apply(time_slot, time_slot_data)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(time_slot)
    return time_slot


def update_time_slots(
    db: Session, items: list[TimeSlotBulkUpdateItem], *, school_id: int
) -> list[TimeSlot]:
    """Several slots at once, all or nothing (the 學校資料 timetable's
    儲存). A slot of another school or a missing one -> 422, nothing
    changed. Returns the school's whole grid afterwards."""
    for item in items:
        time_slot = get_in_school(db, TimeSlot, item.id, school_id)
        if time_slot is None:
            db.rollback()
            raise InvalidReferenceError(
                f"TimeSlot {item.id} does not exist in school {school_id}."
            )
        changes = item.model_dump(exclude_unset=True, exclude={"id"})
        _apply(time_slot, TimeSlotUpdate.model_validate(changes))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    return get_time_slots(db, limit=1000, school_id=school_id)
