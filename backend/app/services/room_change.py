"""Task 95: change the room of lessons already in a DRAFT ScheduleVersion,
then report the version's full schedule check (decision 32).

Rooms are otherwise decided only when a lesson is scheduled or placed; a
room created (or retyped) afterwards could never be used, so the
ROOM_MISSING_FOR_TYPE warning (Task 94) could not be cleared without
rescheduling. Same flow as reassign-teacher (Task 63) and move-lesson
(Task 65): validate (every refusal before anything changes) -> update ->
flush -> the version's check (check_schedule_version(), i.e.
check_assignments()) -> commit, or roll back for dry_run. Any exception
rolls everything back before being re-raised: all or nothing.

Which rows change (`scope`):
- "lesson": the chosen row and, when its lesson is in a lesson block
  (連堂), every row of that block in this version -- a block keeps one room
  (services/block_adjustment.py's Layout.group(), the grouping moves use).
- "requirement": every row of this version for the chosen row's
  requirement.

Only Schedule.room_id changes; teacher and time slot never do. room_id None
clears the room. A missing row or room is refused (404), as is an inactive
room (409, like an inactive teacher for reassign-teacher); a room of
another type than the requirement asks for is not -- H9 reports it, as for
every other conflict (H3 room double-booking included).
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.services import block_adjustment, schedule_check
from app.services.exceptions import (
    AdjustmentTargetNotFoundError,
    InactiveRoomAssignmentError,
    ScheduleNotInVersionError,
)
from app.services.schedule_version import raise_if_version_locked

ConstraintViolation = schedule_check.ConstraintViolation

RoomChangeScope = Literal["lesson", "requirement"]


@dataclass
class RoomChange:
    """One row whose room actually changes; time slot and teacher stay."""

    schedule_id: int
    lesson_id: int
    teacher_id: int | None
    previous_time_slot_id: int | None
    new_time_slot_id: int | None
    previous_room_id: int | None
    new_room_id: int | None


@dataclass
class RoomChangeOutcome:
    # Rows whose room changes, in Schedule.id order. Empty when every row
    # in scope already has that room -- nothing is changed then.
    changes: list[RoomChange]
    violations: list[ConstraintViolation]


def _rows_in_scope(
    db: Session, schedule_version: ScheduleVersion, schedule_id: int, scope: RoomChangeScope
) -> list[int]:
    """The Schedule ids the change applies to, in id order."""
    rows = schedule_check.load_assignment_rows(db, schedule_version.id)
    if scope == "requirement":
        requirement_id = next(a.class_subject_requirement_id for sid, a in rows if sid == schedule_id)
        return [sid for sid, a in rows if a.class_subject_requirement_id == requirement_id]
    layout = block_adjustment.Layout(
        rows,
        schedule_check.load_check_context(db, schedule_version.semester_id, schedule_version.id),
    )
    return sorted(member for _, member in layout.group(schedule_id).members)


def _apply_room(schedule: Schedule, room_id: int | None) -> RoomChange | None:
    """Sets the row's room; the change, or None if it already had it."""
    if schedule.room_id == room_id:
        return None
    change = RoomChange(
        schedule_id=schedule.id,
        lesson_id=schedule.lesson_id,
        teacher_id=schedule.teacher_id,
        previous_time_slot_id=schedule.time_slot_id,
        new_time_slot_id=schedule.time_slot_id,
        previous_room_id=schedule.room_id,
        new_room_id=room_id,
    )
    schedule.room_id = room_id
    return change


def change_room(
    db: Session,
    schedule_version_id: int,
    schedule_id: int,
    room_id: int | None,
    scope: RoomChangeScope,
    *,
    dry_run: bool,
) -> RoomChangeOutcome | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).
    Refusals, in order, before anything changes: a locked version (409),
    the row missing (404) or in another version (409), the room missing
    (404) or inactive (409)."""
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None
    raise_if_version_locked(schedule_version)
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise AdjustmentTargetNotFoundError("Schedule not found")
    if schedule.schedule_version_id != schedule_version_id:
        raise ScheduleNotInVersionError(
            f"Schedule {schedule_id} belongs to ScheduleVersion "
            f"{schedule.schedule_version_id}, not {schedule_version_id}."
        )
    if room_id is not None:
        room = db.get(Room, room_id)
        if room is None:
            raise AdjustmentTargetNotFoundError("Room not found")
        if not room.is_active:
            raise InactiveRoomAssignmentError(f"Room {room_id} is inactive and cannot be assigned.")
    targets = _rows_in_scope(db, schedule_version, schedule_id, scope)

    try:
        changes: list[RoomChange] = []
        for target_id in targets:
            row = db.get(Schedule, target_id)
            assert row is not None  # loaded from this version a moment ago
            change = _apply_room(row, room_id)
            if change is not None:
                changes.append(change)
        db.flush()
        # role=None: the check runs with full (ADMIN) visibility.
        violations = schedule_check.check_schedule_version(db, schedule_version_id)
        assert violations is not None  # the version was found above
        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        # Not swallowed: re-raised after undoing every staged change.
        db.rollback()
        raise
    return RoomChangeOutcome(changes=changes, violations=violations)
