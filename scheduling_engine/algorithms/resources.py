"""Shared building blocks for both scheduling algorithms (Greedy and
Backtracking): the resource bundle they both take as input, and the
candidate-generation helpers that turn a pending Lesson into the set of
(teacher, time_slot, room) combinations worth trying.

Factored out here -- rather than duplicated in greedy.py and
backtracking.py, or having one module import internals from the other --
because both algorithms need EXACTLY the same logic for this part: MRV
candidate-counting and the H5/H6/H9 candidate-narrowing rules don't change
between them. What differs is only how the search itself proceeds once
candidates exist (Greedy: commit to the first valid one and never look
back; Backtracking: same, but retract and try the next one if a later
Lesson gets stuck) -- see greedy.py and backtracking.py.
"""

from dataclasses import dataclass

from scheduling_engine.constraints.active_status import ActiveStatusConstraint
from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.constraints.class_conflict import ClassConflictConstraint
from scheduling_engine.constraints.non_teaching_period import (
    NonTeachingPeriodConstraint,
)
from scheduling_engine.constraints.required_teacher import RequiredTeacherConstraint
from scheduling_engine.constraints.room_conflict import RoomConflictConstraint
from scheduling_engine.constraints.room_type import RoomTypeConstraint
from scheduling_engine.constraints.teacher_availability import (
    TeacherAvailabilityConstraint,
)
from scheduling_engine.constraints.teacher_conflict import TeacherConflictConstraint
from scheduling_engine.constraints.teacher_qualification import (
    TeacherQualificationConstraint,
)
from scheduling_engine.constraints.teacher_workload import TeacherWorkloadConstraint
from scheduling_engine.models.domain import (
    ActiveStatusInfo,
    LessonAssignment,
    RequiredTeacherRule,
    RequirementPeriods,
    RoomInfo,
    RoomTypeRequirement,
    TeacherQualification,
    TeacherUnavailability,
    TeacherWorkloadLimit,
    TimeSlotInfo,
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
    teacher_qualifications: list[TeacherQualification]
    teacher_unavailability: list[TeacherUnavailability]
    required_teacher_rules: list[RequiredTeacherRule]
    room_type_requirements: list[RoomTypeRequirement]
    rooms: list[RoomInfo]
    time_slots: list[TimeSlotInfo]
    active_statuses: list[ActiveStatusInfo]
    requirement_periods: list[RequirementPeriods]
    teacher_workload_limits: list[TeacherWorkloadLimit]


@dataclass(frozen=True)
class LookupTables:
    """The dict form of `SchedulingResources`' list fields, built once per
    algorithm run rather than re-derived for every Lesson (a loop-invariant
    computation, not a performance micro-optimization worth debating)."""

    required_teacher_by_requirement: dict[int, int]
    qualified_teachers_by_subject: dict[int, list[int]]
    required_room_type_by_requirement: dict[int, str]
    room_ids_by_type: dict[str, list[int]]


def build_lookup_tables(resources: SchedulingResources) -> LookupTables:
    required_teacher_by_requirement = {
        rule.class_subject_requirement_id: rule.required_teacher_id
        for rule in resources.required_teacher_rules
    }

    qualified_teachers_by_subject: dict[int, list[int]] = {}
    for qualification in resources.teacher_qualifications:
        qualified_teachers_by_subject.setdefault(qualification.subject_id, []).append(
            qualification.teacher_id
        )

    required_room_type_by_requirement = {
        requirement.class_subject_requirement_id: requirement.required_room_type
        for requirement in resources.room_type_requirements
    }

    room_ids_by_type: dict[str, list[int]] = {}
    for room in resources.rooms:
        room_ids_by_type.setdefault(room.room_type, []).append(room.room_id)

    return LookupTables(
        required_teacher_by_requirement=required_teacher_by_requirement,
        qualified_teachers_by_subject=qualified_teachers_by_subject,
        required_room_type_by_requirement=required_room_type_by_requirement,
        room_ids_by_type=room_ids_by_type,
    )


def candidate_teacher_ids(
    lesson: LessonAssignment, tables: LookupTables
) -> list[int]:
    """H5 (qualification) + H6 (required teacher) combined into the MRV
    candidate count: if a required teacher is pinned for this Lesson's
    requirement, that teacher is the only candidate (count = 1) -- PROVIDED
    they also hold the H5 qualification for this Lesson's subject.
    Otherwise every teacher qualified for the subject is a candidate.

    Task 22: a required teacher who lacks the qualification is not a
    candidate at all (empty list), not a doomed one. H5 is always enforced
    in real time regardless of H6 (see build_real_time_constraints), so a
    required-but-unqualified teacher can never actually be placed -- that
    is a certain, per-Lesson fact, not something that depends on the rest
    of the search. Returning it here as a "candidate" anyway used to let
    such a Lesson slip past the zero-candidate checks that both algorithms
    already rely on (the pre-flight check in backtracking.py, and the
    `if not candidate_teachers` branch in greedy.py's
    _explain_no_valid_candidate), so it could only fail deep inside the
    search where neither algorithm can attribute the failure back to this
    specific Lesson. Filtering it out here instead makes this case
    indistinguishable, everywhere downstream, from "no qualified teacher at
    all" -- the already-correctly-explained case.
    """
    required_teacher_id = tables.required_teacher_by_requirement.get(
        lesson.class_subject_requirement_id
    )
    if required_teacher_id is not None:
        qualified_teachers = tables.qualified_teachers_by_subject.get(
            lesson.subject_id, []
        )
        if required_teacher_id not in qualified_teachers:
            return []
        return [required_teacher_id]
    return list(tables.qualified_teachers_by_subject.get(lesson.subject_id, []))


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
    return list(resources.time_slot_ids)


def candidate_room_ids(
    lesson: LessonAssignment, tables: LookupTables
) -> list[int | None]:
    """H9: if this Lesson's requirement needs a specific room type, only
    rooms of that type are candidates. Otherwise ("原班上課" -- no
    room-type restriction) the only candidate tried is room_id=None."""
    required_room_type = tables.required_room_type_by_requirement.get(
        lesson.class_subject_requirement_id
    )
    if required_room_type is None:
        return [None]
    return list(tables.room_ids_by_type.get(required_room_type, []))


def build_real_time_constraints(
    resources: SchedulingResources, *, include_teacher_workload: bool = False
) -> list[BaseConstraint]:
    """H1-H6, H9, H11, H12 -- the constraints checked against every
    candidate before it's committed.

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
    constraints: list[BaseConstraint] = [
        TeacherConflictConstraint(),
        ClassConflictConstraint(),
        RoomConflictConstraint(),
        TeacherAvailabilityConstraint(resources.teacher_unavailability),
        TeacherQualificationConstraint(resources.teacher_qualifications),
        RequiredTeacherConstraint(resources.required_teacher_rules),
        RoomTypeConstraint(resources.room_type_requirements, resources.rooms),
        NonTeachingPeriodConstraint(resources.time_slots),
        ActiveStatusConstraint(resources.active_statuses),
    ]
    if include_teacher_workload:
        constraints.append(
            TeacherWorkloadConstraint(resources.teacher_workload_limits)
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

    Two distinct root causes share this "zero candidates" shape, so this
    distinguishes them (Task 22) rather than reporting one generic message
    for both:
    - a required-teacher rule (H6) names a teacher who lacks the H5
      qualification for this subject -- the teacher exists, but can never
      be assigned here;
    - no rule pins a teacher at all, and no teacher holds the H5
      qualification for this subject in the first place.
    """
    required_teacher_id = tables.required_teacher_by_requirement.get(
        lesson.class_subject_requirement_id
    )
    if required_teacher_id is not None:
        return ConstraintViolation(
            type="H6_REQUIRED_TEACHER_NOT_QUALIFIED",
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
                f"{required_teacher_id}, but that teacher does not hold a "
                f"TeacherSubject qualification for subject "
                f"{lesson.subject_id}."
            ),
            suggested_action=(
                f"Add a TeacherSubject qualification linking teacher "
                f"{required_teacher_id} to subject {lesson.subject_id}, or "
                "change/remove the required-teacher rule on this "
                "requirement."
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
            f"No teacher is qualified/assignable for lesson "
            f"{lesson.lesson_id} (subject {lesson.subject_id})."
        ),
        suggested_action=("Add a TeacherSubject qualification for this subject."),
    )
