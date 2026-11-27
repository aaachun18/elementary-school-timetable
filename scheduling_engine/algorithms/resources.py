"""Shared building blocks for both scheduling algorithms (Greedy and
Backtracking): the resource bundle they both take as input, and the
candidate-generation helpers that turn a pending Lesson into the set of
(teacher, time_slot, room) combinations worth trying.

Factored out here -- rather than duplicated in greedy.py and
backtracking.py, or having one module import internals from the other --
because both algorithms need EXACTLY the same logic for this part: MRV
candidate-counting and the H6/H9/H13 candidate-narrowing rules don't change
between them. What differs is only how the search itself proceeds once
candidates exist (Greedy: commit to the first valid one and never look
back; Backtracking: same, but retract and try the next one if a later
Lesson gets stuck) -- see greedy.py and backtracking.py.
"""

from dataclasses import dataclass, field

from scheduling_engine.constraints.active_status import ActiveStatusConstraint
from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.constraints.class_conflict import ClassConflictConstraint
from scheduling_engine.constraints.class_time_slot import ClassTimeSlotConstraint
from scheduling_engine.constraints.non_teaching_period import (
    NonTeachingPeriodConstraint,
)
from scheduling_engine.constraints.required_room import RequiredRoomConstraint
from scheduling_engine.constraints.required_teacher import RequiredTeacherConstraint
from scheduling_engine.constraints.requirement_teacher import (
    RequirementSingleTeacherConstraint,
)
from scheduling_engine.constraints.room_conflict import RoomConflictConstraint
from scheduling_engine.constraints.teacher_availability import (
    TeacherAvailabilityConstraint,
)
from scheduling_engine.constraints.teacher_conflict import TeacherConflictConstraint
from scheduling_engine.constraints.teacher_participation import (
    TeacherParticipationConstraint,
)
from scheduling_engine.constraints.teacher_workload import TeacherWorkloadConstraint
from scheduling_engine.constraints.combined_lesson import CombinedLessonConstraint
from scheduling_engine.models.domain import (
    ActiveStatusInfo,
    ClassAllowedTimeSlots,
    CombinedLesson,
    DefaultRoom,
    HomeroomTeacher,
    LessonAssignment,
    LessonBlock,
    RequiredRoomRule,
    RequiredTeacherRule,
    RequirementPeriods,
    RoomCapacity,
    TeacherUnavailability,
    TeacherWorkloadLimit,
    TimeSlotInfo,
    TimeSlotPosition,
    joint_keys,
)


@dataclass(frozen=True)
class SchedulingResources:
    """Every piece of reference data a scheduling algorithm needs beyond
    the Lessons themselves, bundled into one object so the algorithms'
    signatures don't balloon into a dozen separate parameters. Every field
    is exactly the input shape the Task 17/18 constraints already expect --
    this is purely a container, not a new data model.
    """

    time_slot_ids: list[int]
    # Task 98 (replaces the H5 teacher qualifications): the teachers taking
    # part in this semester's scheduling, in the order they are tried. Any
    # of them may teach any lesson -- there is no qualification any more --
    # unless the requirement names a required teacher (H6).
    teacher_ids: list[int]
    teacher_unavailability: list[TeacherUnavailability]
    required_teacher_rules: list[RequiredTeacherRule]
    # Task 98 (replaces the H9 room types): requirement -> its one special
    # room. Its lessons are given this room (it wins over default_rooms),
    # and H9 checks every placement against it.
    required_room_rules: list[RequiredRoomRule]
    time_slots: list[TimeSlotInfo]
    active_statuses: list[ActiveStatusInfo]
    requirement_periods: list[RequirementPeriods]
    teacher_workload_limits: list[TeacherWorkloadLimit]
    # Task 87: both optional -- empty means "no lesson blocks", and every
    # algorithm behaves exactly as before. time_slot_positions is only read
    # for blocks (consecutive periods of one day).
    lesson_blocks: list[LessonBlock] = field(default_factory=list)
    time_slot_positions: list[TimeSlotPosition] = field(default_factory=list)
    # Task 92B: optional -- the homeroom of each requirement held in its
    # class's own room (原班上課). Empty means no homeroom anywhere: a
    # lesson with no required room then gets room None.
    default_rooms: list[DefaultRoom] = field(default_factory=list)
    # Task 98 (H13): optional -- empty means no class is restricted.
    class_allowed_time_slots: list[ClassAllowedTimeSlots] = field(default_factory=list)
    # 共同排課: optional -- every 合併節 (lessons of several classes taught
    # together). Empty means none, and nothing behaves differently.
    combined_lessons: list[CombinedLesson] = field(default_factory=list)
    # H3: how many classes each room holds at once (no entry = 1).
    room_capacities: list[RoomCapacity] = field(default_factory=list)
    # 導師: optional -- empty means no 導師 rule at all (algorithms/homeroom.py).
    homeroom_teachers: list[HomeroomTeacher] = field(default_factory=list)


@dataclass(frozen=True)
class LookupTables:
    """The dict form of `SchedulingResources`' list fields, built once per
    algorithm run rather than re-derived for every Lesson (a loop-invariant
    computation, not a performance micro-optimization worth debating)."""

    required_teacher_by_requirement: dict[int, int]
    teacher_ids: list[int]
    # Task 92B / 98: requirement -> the one room its lessons are held in
    # (its required room, else the class's homeroom).
    default_room_by_requirement: dict[int, int] = field(default_factory=dict)
    # Task 98 (H13): class -> the time slots it may use (absent = any).
    allowed_slots_by_class: dict[int, frozenset[int]] = field(default_factory=dict)
    # 共同排課: lesson -> the room of its combined lesson (lessons of no
    # combined lesson are absent; a combined lesson in a class's own room
    # maps to None).
    combined_room_by_lesson: dict[int, int | None] = field(default_factory=dict)


def room_by_requirement(resources: SchedulingResources) -> dict[int, int]:
    """Task 98: the one room each requirement's lessons are held in -- its
    required room (RequiredRoomRule) where it has one, else its homeroom
    (DefaultRoom). A requirement with neither is absent (room None)."""
    rooms = {item.class_subject_requirement_id: item.room_id for item in resources.default_rooms}
    rooms.update(
        {rule.class_subject_requirement_id: rule.room_id for rule in resources.required_room_rules}
    )
    return rooms


def build_lookup_tables(resources: SchedulingResources) -> LookupTables:
    required_teacher_by_requirement = {
        rule.class_subject_requirement_id: rule.required_teacher_id
        for rule in resources.required_teacher_rules
    }

    return LookupTables(
        required_teacher_by_requirement=required_teacher_by_requirement,
        teacher_ids=list(resources.teacher_ids),
        default_room_by_requirement=room_by_requirement(resources),
        allowed_slots_by_class={
            item.class_id: item.time_slot_ids for item in resources.class_allowed_time_slots
        },
        combined_room_by_lesson={
            lesson_id: combined.room_id
            for combined in resources.combined_lessons
            for lesson_ids in combined.member_lesson_ids
            for lesson_id in lesson_ids
        },
    )


def candidate_teacher_ids(
    lesson: LessonAssignment, tables: LookupTables
) -> list[int]:
    """H6 (required teacher) as the MRV candidate count. Task 98: there is
    no teaching qualification any more -- every teacher taking part in the
    semester's scheduling (resources.teacher_ids) may teach any lesson. A
    required teacher is then the only candidate, PROVIDED they take part in
    the semester; a required teacher who doesn't is no candidate at all
    (empty list): that is a certain, per-Lesson fact, so the zero-candidate
    checks in both algorithms and in static_feasibility.py report it up
    front instead of letting the Lesson fail deep inside the search (the
    Task 22 reasoning, unchanged)."""
    required_teacher_id = tables.required_teacher_by_requirement.get(
        lesson.class_subject_requirement_id
    )
    if required_teacher_id is not None:
        if required_teacher_id not in tables.teacher_ids:
            return []
        return [required_teacher_id]
    return list(tables.teacher_ids)


def allowed_time_slots_of_class(
    class_id: int, resources: SchedulingResources
) -> frozenset[int] | None:
    """H13 (Task 98): the time slots this class may use, or None when it is
    not restricted."""
    for item in resources.class_allowed_time_slots:
        if item.class_id == class_id:
            return item.time_slot_ids
    return None


def candidate_time_slot_ids(
    lesson: LessonAssignment, resources: SchedulingResources
) -> list[int]:
    """Task 28: if this Lesson already has a fixed time slot -- carried as
    the pending LessonAssignment's time_slot_id already being set instead
    of None, the same "a Schedule row can exist before every part of it is
    filled in" convention LessonAssignment already documents -- that is the
    ONLY candidate; there is nothing to search in the time dimension at
    all. Otherwise every school time slot is a candidate, as before.

    Real-time constraints (H1/H2/H3/H4/H9/H11/H12) still run against
    whichever candidate is produced from this list exactly as they do for
    any other candidate, so a fixed slot that conflicts with something else
    is caught the normal way -- this function only narrows WHICH slot(s)
    get tried, never skips validating the one it fixes.
    """
    if lesson.time_slot_id is not None:
        return [lesson.time_slot_id]
    # Task 98 (H13): only the slots the class's grade is open for.
    allowed = allowed_time_slots_of_class(lesson.class_id, resources)
    if allowed is None:
        return list(resources.time_slot_ids)
    return [slot_id for slot_id in resources.time_slot_ids if slot_id in allowed]


def lessons_moved_off_fixed_slot(
    pending: list[LessonAssignment], placed: list[LessonAssignment]
) -> list[int]:
    """Task 81: the lesson_ids of fixed Lessons (pending time_slot_id set)
    whose placed assignment is in a different time slot. Always empty by
    construction -- candidate_time_slot_ids() never offers any other slot --
    and checked once after a successful search so that a future change to
    candidate generation cannot quietly break the guarantee "a fixed Lesson
    is only ever placed in its fixed slot"."""
    fixed_slot_by_lesson = {
        lesson.lesson_id: lesson.time_slot_id
        for lesson in pending
        if lesson.time_slot_id is not None
    }
    return [
        assignment.lesson_id
        for assignment in placed
        if assignment.lesson_id in fixed_slot_by_lesson
        and assignment.time_slot_id != fixed_slot_by_lesson[assignment.lesson_id]
    ]


def candidate_room_ids(
    lesson: LessonAssignment, tables: LookupTables
) -> list[int | None]:
    """H9: the one room this Lesson's requirement is held in -- its required
    room (Task 98), else the class's homeroom (Task 92B), else room_id=None
    when the class has none. Always one candidate: the room is fixed, not a
    search variable -- H3 then keeps two lessons sharing it apart.
    共同排課: a lesson of a combined lesson is held in that one's room."""
    return [room_of_lesson(lesson, tables)]


def room_of_lesson(lesson: LessonAssignment, tables: LookupTables) -> int | None:
    """The one room `lesson` is held in -- see candidate_room_ids()."""
    if lesson.lesson_id in tables.combined_room_by_lesson:
        return tables.combined_room_by_lesson[lesson.lesson_id]
    return tables.default_room_by_requirement.get(lesson.class_subject_requirement_id)


def build_real_time_constraints(
    resources: SchedulingResources, *, include_teacher_workload: bool = False
) -> list[BaseConstraint]:
    """H1-H6, H9, H11-H15 -- the constraints checked against every
    candidate before it's committed (Task 98: H5 is now teacher
    participation, not qualification).

    H8 (`TeacherWorkloadConstraint`) is opt-in via `include_teacher_workload`
    rather than always included: Task 19's Greedy deliberately leaves it out
    (checked only post-hoc, since Greedy can't recover from a bad early
    choice anyway); Task 20's Backtracking passes True, since a ceiling
    constraint like H8 is safe to filter on in real time (see
    backtracking.py's module docstring) and doing so lets the search avoid
    committing to a doomed branch in the first place. H7 is never included
    here at all -- it is mathematically impossible to check per-candidate
    (see weekly_periods.py's docstring) and is always a separate,
    whole-batch, post-hoc step in both algorithms.
    """
    keys = joint_keys(resources.combined_lessons)
    constraints: list[BaseConstraint] = [
        TeacherConflictConstraint(keys),
        ClassConflictConstraint(),
        RoomConflictConstraint(resources.room_capacities, keys),
        TeacherAvailabilityConstraint(resources.teacher_unavailability),
        TeacherParticipationConstraint(resources.teacher_ids),
        RequiredTeacherConstraint(resources.required_teacher_rules),
        # H15: one teacher for all lessons of a requirement.
        RequirementSingleTeacherConstraint(),
        RequiredRoomConstraint(resources.required_room_rules, frozenset(keys)),
        NonTeachingPeriodConstraint(resources.time_slots),
        ActiveStatusConstraint(resources.active_statuses),
        ClassTimeSlotConstraint(resources.class_allowed_time_slots),
    ]
    if resources.combined_lessons:
        constraints.append(CombinedLessonConstraint(resources.combined_lessons))
    if include_teacher_workload:
        constraints.append(
            TeacherWorkloadConstraint(resources.teacher_workload_limits, keys)
        )
    return constraints


@dataclass
class LessonFailure:
    """Why one specific Lesson could not be placed at all."""

    lesson_id: int
    class_subject_requirement_id: int
    reasons: list[ConstraintViolation]


def no_candidate_teacher_violation(
    lesson: LessonAssignment, tables: LookupTables
) -> ConstraintViolation:
    """A synthetic violation for the case where a Lesson has zero candidate
    teachers at all -- there's nothing to run explain_violations() against,
    since no candidate could even be constructed.

    Task 98: two root causes share this "zero candidates" shape, so this
    distinguishes them (the Task 22 split, with qualifications gone):
    - a required-teacher rule (H6) names a teacher who doesn't take part in
      the semester's scheduling;
    - no rule pins a teacher, and no teacher takes part at all.
    """
    required_teacher_id = tables.required_teacher_by_requirement.get(
        lesson.class_subject_requirement_id
    )
    if required_teacher_id is not None:
        return ConstraintViolation(
            type="H6_REQUIRED_TEACHER_NOT_PARTICIPATING",
            severity=Severity.ERROR,
            lesson_id=lesson.lesson_id,
            teacher_id=required_teacher_id,
            class_id=lesson.class_id,
            subject_id=lesson.subject_id,
            time_slot_id=None,
            room_id=None,
            class_subject_requirement_id=lesson.class_subject_requirement_id,
            message=(
                f"Lesson {lesson.lesson_id} requires teacher "
                f"{required_teacher_id}, but that teacher does not take part "
                "in this semester's scheduling."
            ),
            suggested_action=(
                f"Add teacher {required_teacher_id} to this semester's "
                "teachers, or change/remove the required-teacher rule on "
                "this requirement."
            ),
        )
    return ConstraintViolation(
        type="NO_CANDIDATE_TEACHER",
        severity=Severity.ERROR,
        lesson_id=lesson.lesson_id,
        teacher_id=None,
        class_id=lesson.class_id,
        subject_id=lesson.subject_id,
        time_slot_id=None,
        room_id=None,
        class_subject_requirement_id=lesson.class_subject_requirement_id,
        message=(
            f"No teacher takes part in this semester's scheduling, so lesson "
            f"{lesson.lesson_id} (subject {lesson.subject_id}) has no teacher."
        ),
        suggested_action="Add teachers to this semester's scheduling.",
    )
