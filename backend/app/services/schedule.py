from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import PUBLISHED, ScheduleVersion
from app.models.teacher import Teacher
from app.models.time_slot import TimeSlot
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.schedule_version import raise_if_version_locked
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)


def _ensure_references_in_school(
    db: Session, school_id: int, fields: dict[str, object]
) -> None:
    """Task 98: everything a Schedule row points at must be of the
    caller's school."""
    references: list[tuple[type, int | None]] = [
        (model, fields.get(field))  # type: ignore[misc]
        for model, field in (
            (ScheduleVersion, "schedule_version_id"),
            (Lesson, "lesson_id"),
            (Teacher, "teacher_id"),
            (TimeSlot, "time_slot_id"),
            (Room, "room_id"),
        )
    ]
    ensure_references_in_school(db, school_id, references)


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


def create_schedule(
    db: Session, schedule_data: ScheduleCreate, *, school_id: int
) -> Schedule:
    _ensure_references_in_school(db, school_id, schedule_data.model_dump())
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
    db: Session, schedule_id: int, *, school_id: int, role: str | None = None
) -> Schedule | None:
    """Task 43: same TEACHER-only-sees-PUBLISHED filter as
    schedule_version.get_schedule_version() -- a Schedule belonging to a
    DRAFT version resolves to None (-> the router's existing 404) for
    TEACHER, never a separate 403. `role=None` (every other caller) sees
    every Schedule of the school."""
    schedule = get_in_school(db, Schedule, schedule_id, school_id)
    if schedule is None:
        return None
    if role == "TEACHER":
        version = db.get(ScheduleVersion, schedule.schedule_version_id)
        if version is None or version.status != PUBLISHED:
            return None
    return schedule


def get_schedules(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    *,
    school_id: int,
    schedule_version_id: int | None = None,
    role: str | None = None,
) -> list[Schedule]:
    """Task 66: optional schedule_version_id filter. A version that doesn't
    exist -- or, for TEACHER, isn't PUBLISHED -- simply matches no rows
    (empty list, never a 404), so the filter can't reveal whether a hidden
    version exists. Ordered by id so skip/limit pages are stable."""
    stmt = select(Schedule).where(in_school(Schedule, school_id))
    if schedule_version_id is not None:
        stmt = stmt.where(Schedule.schedule_version_id == schedule_version_id)
    if role == "TEACHER":
        stmt = stmt.join(
            ScheduleVersion, Schedule.schedule_version_id == ScheduleVersion.id
        ).where(ScheduleVersion.status == PUBLISHED)
    stmt = stmt.order_by(Schedule.id).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_schedule(
    db: Session, schedule_id: int, schedule_data: ScheduleUpdate, *, school_id: int
) -> Schedule | None:
    schedule = get_in_school(db, Schedule, schedule_id, school_id)
    if schedule is None:
        return None

    _raise_if_published(db, schedule)

    changes = schedule_data.model_dump(exclude_unset=True)
    _ensure_references_in_school(db, school_id, changes)
    for field, value in changes.items():
        setattr(schedule, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule_id: int, *, school_id: int) -> bool:
    schedule = get_in_school(db, Schedule, schedule_id, school_id)
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
