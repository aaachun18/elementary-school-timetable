from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.models.schedule_version import PUBLISHED, ScheduleVersion
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.schedule_version import raise_if_version_locked


def _raise_if_version_published(db: Session, schedule_version_id: int) -> None:
    """Task 25/25.5: a Schedule row -- new or existing -- belonging to a
    PUBLISHED (Task 64: or ARCHIVED) ScheduleVersion is locked, same as the
    version itself.
    schedule_version_id is always set on a Schedule (see
    app/models/schedule.py), so this lookup never needs a None check the
    way an optional FK would."""
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is not None:
        raise_if_version_locked(schedule_version)


def _raise_if_published(db: Session, schedule: Schedule) -> None:
    _raise_if_version_published(db, schedule.schedule_version_id)


def create_schedule(db: Session, schedule_data: ScheduleCreate) -> Schedule:
    _raise_if_version_published(db, schedule_data.schedule_version_id)

    schedule = Schedule(**schedule_data.model_dump())
    db.add(schedule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(schedule)
    return schedule


def get_schedule(
    db: Session, schedule_id: int, *, role: str | None = None
) -> Schedule | None:
    """Task 43: same TEACHER-only-sees-PUBLISHED filter as
    schedule_version.get_schedule_version() -- a Schedule belonging to a
    DRAFT version resolves to None (-> the router's existing 404) for
    TEACHER, never a separate 403. `role=None` (every other caller) sees
    every Schedule, unfiltered."""
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        return None
    if role == "TEACHER":
        version = db.get(ScheduleVersion, schedule.schedule_version_id)
        if version is None or version.status != PUBLISHED:
            return None
    return schedule


def get_schedules(
    db: Session, skip: int = 0, limit: int = 100, *, role: str | None = None
) -> list[Schedule]:
    stmt = select(Schedule)
    if role == "TEACHER":
        stmt = stmt.join(
            ScheduleVersion, Schedule.schedule_version_id == ScheduleVersion.id
        ).where(ScheduleVersion.status == PUBLISHED)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_schedule(
    db: Session, schedule_id: int, schedule_data: ScheduleUpdate
) -> Schedule | None:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        return None

    _raise_if_published(db, schedule)

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

    _raise_if_published(db, schedule)

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
