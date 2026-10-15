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

A move keeps the row's room and only changes its time slot, and a swap
exchanges the two rows' time slots (each keeps its teacher and room) --
exactly what move-lesson (with no target room) and swap-lessons do, so for
the same data each `move`/`swaps` entry equals that endpoint's dry_run
check (tests/test_move_candidates.py compares them slot by slot).
"""

from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.time_slot import TimeSlot
from app.services import schedule_check
from app.services.exceptions import AdjustmentTargetNotFoundError
from app.services.schedule_version import raise_if_version_locked

ConstraintViolation = schedule_check.ConstraintViolation
LessonAssignment = schedule_check.LessonAssignment

# Why a time slot is not a move target. The frontend's own rule
# (utils/lessonDrop.ts canMoveLessonTo) is the same.
NON_TEACHING_SLOT = "NON_TEACHING_SLOT"
CURRENT_SLOT = "CURRENT_SLOT"


@dataclass
class SwapCandidate:
    swap_with_schedule_id: int
    violations: list[ConstraintViolation]


@dataclass
class SlotCandidate:
    time_slot_id: int
    available: bool
    unavailable_reason: str | None
    # None when the slot is not a move target (see unavailable_reason).
    move: list[ConstraintViolation] | None
    swaps: list[SwapCandidate]


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

    base = [assignment for _, assignment in rows]
    index = next(i for i, (row_id, _) in enumerate(rows) if row_id == schedule_id)
    lesson = base[index]
    current_slot = lesson.time_slot_id

    def check_with(changes: dict[int, int | None]) -> list[ConstraintViolation]:
        """The check after setting time_slot_id on the rows at these
        positions; every other row as stored."""
        arranged = [
            replace(assignment, time_slot_id=changes[i]) if i in changes else assignment
            for i, assignment in enumerate(base)
        ]
        return schedule_check.check_assignments(context, arranged)

    candidates: list[SlotCandidate] = []
    for time_slot in time_slots:
        if time_slot.id == current_slot:
            candidates.append(
                SlotCandidate(time_slot.id, False, CURRENT_SLOT, None, [])
            )
            continue
        swaps = [
            SwapCandidate(
                swap_with_schedule_id=row_id,
                violations=check_with({index: time_slot.id, other_index: current_slot}),
            )
            for other_index, (row_id, other) in enumerate(rows)
            if other_index != index
            and other.time_slot_id == time_slot.id
            and _is_swap_partner(lesson, other)
        ]
        if not time_slot.is_teaching_period:
            candidates.append(
                SlotCandidate(time_slot.id, False, NON_TEACHING_SLOT, None, swaps)
            )
            continue
        candidates.append(
            SlotCandidate(
                time_slot.id, True, None, check_with({index: time_slot.id}), swaps
            )
        )

    return MoveCandidatesOutcome(
        schedule_id=schedule_id,
        current_time_slot_id=current_slot,
        baseline=schedule_check.check_assignments(context, base),
        candidates=candidates,
    )
