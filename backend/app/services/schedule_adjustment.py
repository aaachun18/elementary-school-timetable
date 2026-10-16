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

Task 89: a lesson in a lesson block (連堂) takes its whole block with it.
Which rows go where is decided by services/block_adjustment.py -- the same
plan move-candidates uses -- before anything changes; a plan the rules
refuse raises BlockAdjustmentRefusedError (-> 409), and otherwise every
planned row is updated in the one transaction (all or nothing). A lesson of
no block plans to exactly the one row (two for a swap) these endpoints
always changed.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.time_slot import TimeSlot
from app.services import block_adjustment, schedule_check
from app.services.exceptions import (
    AdjustmentTargetNotFoundError,
    BlockAdjustmentRefusedError,
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


def _plan(
    db: Session,
    schedule_version: ScheduleVersion,
    make_plan: Callable[[block_adjustment.Layout], block_adjustment.Plan],
) -> block_adjustment.Plan:
    """Task 89: the plan for this change, from the version's rows as
    stored; raises BlockAdjustmentRefusedError (nothing changed yet) when
    the block rules refuse it."""
    layout = block_adjustment.Layout(
        schedule_check.load_assignment_rows(db, schedule_version.id),
        schedule_check.load_check_context(db, schedule_version.semester_id, schedule_version.id),
    )
    plan = make_plan(layout)
    if plan.refusal is not None:
        raise BlockAdjustmentRefusedError(plan.refusal)
    return plan


def _apply_plan(
    db: Session, plan: block_adjustment.Plan, room_ids: dict[int, int]
) -> list[ScheduleChange]:
    """Every planned row to its slot (room from room_ids, default: its
    own), in plan order; returns the rows that actually changed."""
    assert plan.slots is not None
    changes: list[ScheduleChange] = []
    for planned in plan.slots:
        schedule = db.get(Schedule, planned.schedule_id)
        assert schedule is not None  # loaded from this version a moment ago
        change = _apply(
            schedule, planned.time_slot_id, room_ids.get(planned.schedule_id, schedule.room_id)
        )
        if change is not None:
            changes.append(change)
    return changes


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
    turned into a swap -- that's swap_lessons()'s job (for a block such a
    target is refused: BLOCK_TARGET_OCCUPIED). Task 89: a lesson in a block
    moves with its whole block; a target room then applies to all of it."""
    schedule_version = _get_unlocked_version(db, schedule_version_id)
    if schedule_version is None:
        return None
    _get_schedule_in_version(db, schedule_version_id, schedule_id)
    if db.get(TimeSlot, target_time_slot_id) is None:
        raise AdjustmentTargetNotFoundError("TimeSlot not found")
    if target_room_id is not None and db.get(Room, target_room_id) is None:
        raise AdjustmentTargetNotFoundError("Room not found")
    plan = _plan(
        db, schedule_version, lambda layout: layout.plan_move(schedule_id, target_time_slot_id)
    )

    try:
        assert plan.slots is not None
        room_ids = (
            {}
            if target_room_id is None
            else {planned.schedule_id: target_room_id for planned in plan.slots}
        )
        changes = _apply_plan(db, plan, room_ids)
        violations = _flush_check_and_finish(db, schedule_version_id, dry_run=dry_run)
    except Exception:
        # Not swallowed: re-raised after undoing every staged change.
        db.rollback()
        raise
    return AdjustmentOutcome(changes=changes, violations=violations)


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
    room. Two rows already in the same slot produce no changes. Task 89:
    with a block involved the two whole groups exchange places (see
    services/block_adjustment.py), or BlockAdjustmentRefusedError."""
    schedule_version = _get_unlocked_version(db, schedule_version_id)
    if schedule_version is None:
        return None
    if schedule_id == swap_with_schedule_id:
        raise CannotSwapWithSelfError(f"Schedule {schedule_id} cannot swap with itself.")
    _get_schedule_in_version(db, schedule_version_id, schedule_id)
    _get_schedule_in_version(db, schedule_version_id, swap_with_schedule_id)
    plan = _plan(
        db, schedule_version, lambda layout: layout.plan_swap(schedule_id, swap_with_schedule_id)
    )

    try:
        changes = _apply_plan(db, plan, {})
        violations = _flush_check_and_finish(db, schedule_version_id, dry_run=dry_run)
    except Exception:
        db.rollback()
        raise
    return AdjustmentOutcome(changes=changes, violations=violations)
