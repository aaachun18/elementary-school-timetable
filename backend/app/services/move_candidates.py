"""Task 83: for one lesson (one Schedule row) of a DRAFT ScheduleVersion,
what the version's schedule check would report after moving it to each
time slot -- or swapping it with each lesson it could be swapped with there.
The timetable's edit mode uses this to mark candidate cells while a lesson
is selected or dragged.

Read-only and in memory: the version's rows, requirements and fixed slots
are loaded ONCE (services/schedule_check.py's load_check_context() and
load_assignment_rows()), then every hypothetical arrangement is checked by
the same pure check_assignments() that GET /check runs. Nothing is written
or flushed -- not even temporarily -- so there is nothing to roll back.

Which rows a move or a swap changes comes from services/block_adjustment.py
(Task 89) -- the very plan move-lesson (with no target room) and
swap-lessons apply -- so for the same data each `move`/`swaps` entry equals
that endpoint's dry_run check (tests/test_move_candidates.py and
tests/test_block_adjustment.py compare them slot by slot). For a lesson in a
lesson block (連堂) the whole block moves; a target the block rules refuse
is not available (BLOCK_OUT_OF_RANGE / BLOCK_TARGET_OCCUPIED), and a swap
they refuse is listed in unsupported_swaps instead of swaps.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.time_slot import TimeSlot
from app.services import block_adjustment, schedule_check
from app.services.exceptions import AdjustmentTargetNotFoundError
from app.services.schedule_version import raise_if_version_locked

ConstraintViolation = schedule_check.ConstraintViolation
LessonAssignment = schedule_check.LessonAssignment

# Why a time slot is not a move target. The frontend's own rule
# (utils/lessonDrop.ts canMoveLessonTo) is the same for the first two;
# the block ones come from services/block_adjustment.py (Task 89).
# Task 92: defined in block_adjustment.py, which placement shares it from.
NON_TEACHING_SLOT = block_adjustment.NON_TEACHING_SLOT
CURRENT_SLOT = "CURRENT_SLOT"


@dataclass
class BlockMember:
    """Task 89: one row that moves with a change of a block."""

    schedule_id: int
    to_time_slot_id: int | None


@dataclass
class SwapCandidate:
    swap_with_schedule_id: int
    violations: list[ConstraintViolation]
    # Task 89: every row the swap moves, when a block is involved; None
    # for two lessons of no block (only the two rows exchange slots).
    block_members: list[BlockMember] | None = None


@dataclass
class UnsupportedSwap:
    """Task 89: a lesson in this slot the selected one can't be swapped
    with under the block rules (reason BLOCK_SWAP_UNSUPPORTED)."""

    swap_with_schedule_id: int
    reason: str


@dataclass
class SlotCandidate:
    time_slot_id: int
    available: bool
    unavailable_reason: str | None
    # None when the slot is not a move target (see unavailable_reason).
    move: list[ConstraintViolation] | None
    swaps: list[SwapCandidate]
    # Task 89: where every lesson of the selected lesson's block goes for
    # this move; None for a lesson of no block or a slot that is no target.
    block_members: list[BlockMember] | None = None
    # Task 89: None when there is none.
    unsupported_swaps: list[UnsupportedSwap] | None = None


@dataclass
class MoveCandidatesOutcome:
    schedule_id: int
    current_time_slot_id: int | None
    baseline: list[ConstraintViolation]
    candidates: list[SlotCandidate]


def _is_swap_partner(lesson: LessonAssignment, other: LessonAssignment) -> bool:
    """A lesson the timetable could show in the same cell as `lesson` in one
    of its three views -- same class (class view), same teacher (teacher
    view) or same room (room view). The frontend picks the ones of the view
    it is showing; the backend's swap-lessons itself accepts any row."""
    return (
        other.class_id == lesson.class_id
        or (lesson.teacher_id is not None and other.teacher_id == lesson.teacher_id)
        or (lesson.room_id is not None and other.room_id == lesson.room_id)
    )


def _members(plan: block_adjustment.Plan) -> list[BlockMember]:
    assert plan.slots is not None
    return [BlockMember(planned.schedule_id, planned.time_slot_id) for planned in plan.slots]


def list_move_candidates(
    db: Session, schedule_version_id: int, schedule_id: int
) -> MoveCandidatesOutcome | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).
    Raises PublishedVersionImmutableError / ArchivedVersionImmutableError
    (-> 409) for a locked version, and AdjustmentTargetNotFoundError
    (-> 404) when the Schedule row doesn't exist OR belongs to another
    version -- a read-only lookup, so a foreign row is simply "not found
    here" rather than move-lesson's 409."""
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None
    raise_if_version_locked(schedule_version)
    schedule = db.get(Schedule, schedule_id)
    if schedule is None or schedule.schedule_version_id != schedule_version_id:
        raise AdjustmentTargetNotFoundError("Schedule not found")

    context = schedule_check.load_check_context(
        db, schedule_version.semester_id, schedule_version_id
    )
    rows = schedule_check.load_assignment_rows(db, schedule_version_id)
    time_slots = db.scalars(
        select(TimeSlot).order_by(TimeSlot.weekday, TimeSlot.period, TimeSlot.id)
    ).all()
    layout = block_adjustment.Layout(rows, context)

    lesson = layout.assignment[schedule_id]
    current_slot = lesson.time_slot_id
    in_block = layout.is_in_block(schedule_id)

    def check_after(plan: block_adjustment.Plan) -> list[ConstraintViolation]:
        return schedule_check.check_assignments(context, block_adjustment.arranged(rows, plan))

    candidates: list[SlotCandidate] = []
    for time_slot in time_slots:
        if time_slot.id == current_slot:
            candidates.append(
                SlotCandidate(time_slot.id, False, CURRENT_SLOT, None, [])
            )
            continue
        swaps: list[SwapCandidate] = []
        unsupported: list[UnsupportedSwap] = []
        for row_id, other in rows:
            if (
                row_id == schedule_id
                or other.time_slot_id != time_slot.id
                or not _is_swap_partner(lesson, other)
            ):
                continue
            plan = layout.plan_swap(schedule_id, row_id)
            if plan.refusal is not None:
                unsupported.append(UnsupportedSwap(row_id, plan.refusal))
                continue
            block_involved = in_block or layout.is_in_block(row_id)
            swaps.append(
                SwapCandidate(
                    swap_with_schedule_id=row_id,
                    violations=check_after(plan),
                    block_members=_members(plan) if block_involved else None,
                )
            )
        unsupported_swaps = unsupported or None
        if not time_slot.is_teaching_period:
            candidates.append(
                SlotCandidate(
                    time_slot.id, False, NON_TEACHING_SLOT, None, swaps,
                    unsupported_swaps=unsupported_swaps,
                )
            )
            continue
        plan = layout.plan_move(schedule_id, time_slot.id)
        if plan.refusal is not None:
            candidates.append(
                SlotCandidate(
                    time_slot.id, False, plan.refusal, None, swaps,
                    unsupported_swaps=unsupported_swaps,
                )
            )
            continue
        candidates.append(
            SlotCandidate(
                time_slot.id,
                True,
                None,
                check_after(plan),
                swaps,
                block_members=_members(plan) if in_block else None,
                unsupported_swaps=unsupported_swaps,
            )
        )

    return MoveCandidatesOutcome(
        schedule_id=schedule_id,
        current_time_slot_id=current_slot,
        baseline=schedule_check.check_assignments(context, [a for _, a in rows]),
        candidates=candidates,
    )
