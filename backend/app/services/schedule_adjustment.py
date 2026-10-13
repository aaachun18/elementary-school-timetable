"""Task 65: move one lesson to another time slot, or swap the time slots of
two lessons, within a DRAFT ScheduleVersion -- then report the version's
full schedule check.

Manual adjustments, same shape as reassign-teacher (Task 63): validate
(every refusal before anything changes) -> update -> flush -> run the
schedule check -> commit, or roll back for dry_run. Any exception rolls
everything back before being re-raised.

Only Schedule.time_slot_id changes (plus room_id, for a move that names a
target room). Teacher and room belong to the lesson, so in a swap each
stays on its own row. Lesson (including fixed_time_slot_id) and the
requirements are never touched. Conflicts -- teacher/class/room double-
booking, unavailable slots, a lesson moved off its fixed slot -- never
block: the returned check lists them.

Schedule's only unique constraint is (schedule_version_id, lesson_id);
nothing is unique on time_slot_id, so a swap can update both rows directly
without any intermediate-state trick.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.time_slot import TimeSlot
from app.services import schedule_check
from app.services.exceptions import (
    AdjustmentTargetNotFoundError,
    CannotSwapWithSelfError,
    ScheduleNotInVersionError,
)
from app.services.schedule_version import raise_if_version_locked

# See services/teacher_reassignment.py for why this alias exists.
ConstraintViolation = schedule_check.ConstraintViolation


@dataclass
class ScheduleChange:
    """One Schedule row whose time slot and/or room actually changed."""

    schedule_id: int
    previous_time_slot_id: int | None
    new_time_slot_id: int | None
    previous_room_id: int | None
    new_room_id: int | None


@dataclass
class AdjustmentOutcome:
    changes: list[ScheduleChange]
    violations: list[ConstraintViolation]


def _get_unlocked_version(db: Session, schedule_version_id: int) -> ScheduleVersion | None:
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is not None:
        raise_if_version_locked(schedule_version)
    return schedule_version


def _get_schedule_in_version(
    db: Session, schedule_version_id: int, schedule_id: int
) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise AdjustmentTargetNotFoundError("Schedule not found")
    if schedule.schedule_version_id != schedule_version_id:
        raise ScheduleNotInVersionError(
            f"Schedule {schedule_id} belongs to ScheduleVersion "
            f"{schedule.schedule_version_id}, not {schedule_version_id}."
        )
    return schedule


def _apply(
    schedule: Schedule, new_time_slot_id: int | None, new_room_id: int | None
) -> ScheduleChange | None:
    """Sets the row's time slot and room; returns the change, or None if
    both were already those values."""
    if schedule.time_slot_id == new_time_slot_id and schedule.room_id == new_room_id:
        return None
    change = ScheduleChange(
        schedule_id=schedule.id,
        previous_time_slot_id=schedule.time_slot_id,
        new_time_slot_id=new_time_slot_id,
        previous_room_id=schedule.room_id,
        new_room_id=new_room_id,
    )
    schedule.time_slot_id = new_time_slot_id
    schedule.room_id = new_room_id
    return change


def _flush_check_and_finish(
    db: Session, schedule_version_id: int, *, dry_run: bool
) -> list[ConstraintViolation]:
    db.flush()
    # role=None: the check runs with full (ADMIN) visibility.
    violations = schedule_check.check_schedule_version(db, schedule_version_id)
    assert violations is not None  # the version was found by the caller
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return violations


def move_lesson(
    db: Session,
    schedule_version_id: int,
    schedule_id: int,
    target_time_slot_id: int,
    target_room_id: int | None,
    *,
    dry_run: bool,
) -> AdjustmentOutcome | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).
    target_room_id None means "keep the current room" (this API cannot
    clear a room). Moving to the current slot (and room) is a no-op with
    no changes. A slot where the class already has another lesson is NOT
    turned into a swap -- that's swap_lessons()'s job."""
    schedule_version = _get_unlocked_version(db, schedule_version_id)
    if schedule_version is None:
        return None
    schedule = _get_schedule_in_version(db, schedule_version_id, schedule_id)
    if db.get(TimeSlot, target_time_slot_id) is None:
        raise AdjustmentTargetNotFoundError("TimeSlot not found")
    if target_room_id is not None and db.get(Room, target_room_id) is None:
        raise AdjustmentTargetNotFoundError("Room not found")

    try:
        new_room_id = schedule.room_id if target_room_id is None else target_room_id
        change = _apply(schedule, target_time_slot_id, new_room_id)
        violations = _flush_check_and_finish(db, schedule_version_id, dry_run=dry_run)
    except Exception:
        # Not swallowed: re-raised after undoing every staged change.
        db.rollback()
        raise
    return AdjustmentOutcome(
        changes=[change] if change is not None else [], violations=violations
    )


def swap_lessons(
    db: Session,
    schedule_version_id: int,
    schedule_id: int,
    swap_with_schedule_id: int,
    *,
    dry_run: bool,
) -> AdjustmentOutcome | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).
    The two rows exchange time_slot_id; each keeps its own teacher and
    room. Two rows already in the same slot produce no changes."""
    schedule_version = _get_unlocked_version(db, schedule_version_id)
    if schedule_version is None:
        return None
    if schedule_id == swap_with_schedule_id:
        raise CannotSwapWithSelfError(f"Schedule {schedule_id} cannot swap with itself.")
    first = _get_schedule_in_version(db, schedule_version_id, schedule_id)
    second = _get_schedule_in_version(db, schedule_version_id, swap_with_schedule_id)

    try:
        first_slot, second_slot = first.time_slot_id, second.time_slot_id
        changes = [
            change
            for change in (
                _apply(first, second_slot, first.room_id),
                _apply(second, first_slot, second.room_id),
            )
            if change is not None
        ]
        violations = _flush_check_and_finish(db, schedule_version_id, dry_run=dry_run)
    except Exception:
        db.rollback()
        raise
    return AdjustmentOutcome(changes=changes, violations=violations)
