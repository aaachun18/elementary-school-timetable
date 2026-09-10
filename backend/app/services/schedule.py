from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_schedule(db: Session, schedule_data: ScheduleCreate) -> Schedule:
    schedule = Schedule(**schedule_data.model_dump())
    db.add(schedule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(schedule)
    return schedule


def get_schedule(db: Session, schedule_id: int) -> Schedule | None:
    return db.get(Schedule, schedule_id)


def get_schedules(db: Session, skip: int = 0, limit: int = 100) -> list[Schedule]:
    stmt = select(Schedule).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_schedule(
    db: Session, schedule_id: int, schedule_data: ScheduleUpdate
) -> Schedule | None:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        return None

    for field, value in schedule_data.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule_id: int) -> bool:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        return False

    try:
        db.delete(schedule)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Schedule {schedule_id} cannot be deleted: other records "
            "still reference it."
        ) from exc

    return True
