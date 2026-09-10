"""Greedy Scheduler.

For each Lesson (processed in MRV order -- fewest candidate teachers
first), pick the first (teacher, time_slot, room) combination that
satisfies every *real-time* Hard Constraint: H1-H6, H9, H11, H12. If no
Lesson-level candidate exists, the whole run fails atomically -- no partial
schedule is ever returned (see GreedyResult).

Why H7/H8 are checked once at the end, not per-candidate
----------------------------------------------------------
H1-H6/H9/H11/H12 all ask "is THIS SPECIFIC candidate okay, given what's
already been placed?" -- a question that has a definite yes/no answer the
moment you look at one more assignment on top of the current state. That's
exactly what real-time, per-candidate filtering needs.

H7 ("this requirement has *exactly* N scheduled lessons") and H8 ("this
teacher has *at most* N scheduled lessons") are different in kind, not just
in scope:

- H8 is a ceiling (`<=`). In principle a ceiling COULD be checked
  incrementally -- "would adding this candidate push the teacher over
  their max?" -- and once satisfied it stays satisfied as more assignments
  are added elsewhere (Greedy only ever adds, never removes). So real-time
  H8 filtering is technically possible.
- H7 is an exact target (`==`). It is *mathematically* unsatisfiable until
  the LAST lesson for that requirement has been placed -- every
  in-progress state with 1 of 3 lessons placed necessarily has
  actual_count < target, which would look identical to a genuine shortfall
  if checked mid-way. There is no way to check H7 "per candidate" without
  producing false positives on every requirement that isn't finished yet.
  It is inherently a whole-batch, end-of-run property.

Given that asymmetry, this implementation's decision (open for discussion,
not asserted as the only valid answer -- see the Task 19 report) is to
keep BOTH H7 and H8 as post-hoc-only BaseConstraint checks, exactly as
scoped: `_build_real_time_constraints()` below returns only the 9
constraints that make sense as per-candidate filters, and
`WeeklyPeriodsConstraint`/`TeacherWorkloadConstraint` are invoked exactly
once, after every Lesson has a placement, over the complete assignment
list. This is the simplest correct design that matches the given
algorithm outline; an alternative worth considering for a future Task is
adding a *separate*, non-constraint-based pruning heuristic to candidate
generation (skip a teacher who's already at their cap when there's more
than one candidate teacher to choose from) purely as a greedy-quality
optimization -- see the report for the full trade-off discussion. That
optimization is NOT implemented here, so it is possible (and covered by a
test) for a completed run to fail the post-hoc H8 check.
"""

from dataclasses import dataclass, replace

from scheduling_engine.constraints.active_status import ActiveStatusConstraint
from scheduling_engine.constraints.base import BaseConstraint, ConstraintViolation, Severity
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
from scheduling_engine.constraints.weekly_periods import WeeklyPeriodsConstraint
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
from scheduling_engine.state import SchedulingState


@dataclass(frozen=True)
class SchedulingResources:
    """Every piece of reference data the Greedy algorithm needs beyond the
    Lessons themselves, bundled into one object so schedule_greedy()'s
    signature doesn't balloon into a dozen separate parameters. Every field
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


@dataclass
class LessonFailure:
    """Why one specific Lesson could not be placed at all."""

    lesson_id: int
    class_subject_requirement_id: int
    reasons: list[ConstraintViolation]


@dataclass
class GreedyResult:
    """success=False means NO schedule was produced: `state` is None, on
    purpose -- this algorithm never returns a partial result a caller
    might mistake for a usable schedule (the atomicity the Task asks for).

    On failure, exactly one of the two lists is populated:
    - lesson_failures: at least one Lesson had no valid candidate at all
      (a real-time constraint problem). state is None; the run stopped
      committing new assignments, but still attempted every remaining
      Lesson (against whatever was placed before the first failure) so
      this list reports every Lesson that failed, not just the first.
    - post_hoc_violations: every Lesson found a candidate, but the
      finished schedule still fails H7 (wrong lesson count for some
      requirement) or H8 (a teacher over their workload cap).
    """

    success: bool
    state: SchedulingState | None
    lesson_failures: list[LessonFailure]
    post_hoc_violations: list[ConstraintViolation]


def _candidate_teacher_ids(
    lesson: LessonAssignment,
    required_teacher_by_requirement: dict[int, int],
    qualified_teachers_by_subject: dict[int, list[int]],
) -> list[int]:
    """H5 (qualification) + H6 (required teacher) combined into the MRV
    candidate count: if a required teacher is pinned for this Lesson's
    requirement, that teacher is the only candidate (count = 1, per the
    MRV rule as given); otherwise every teacher qualified for the subject
    is a candidate."""
    required_teacher_id = required_teacher_by_requirement.get(
        lesson.class_subject_requirement_id
    )
    if required_teacher_id is not None:
        return [required_teacher_id]
    return list(qualified_teachers_by_subject.get(lesson.subject_id, []))


def _candidate_room_ids(
    lesson: LessonAssignment,
    required_room_type_by_requirement: dict[int, str],
    room_ids_by_type: dict[str, list[int]],
) -> list[int | None]:
    """H9: if this Lesson's requirement needs a specific room type, only
    rooms of that type are candidates. Otherwise ("原班上課" -- no
    room-type restriction) the only candidate tried is room_id=None; there
    is no reason to search over every real room when none is actually
    required."""
    required_room_type = required_room_type_by_requirement.get(
        lesson.class_subject_requirement_id
    )
    if required_room_type is None:
        return [None]
    return list(room_ids_by_type.get(required_room_type, []))


def _build_real_time_constraints(
    resources: SchedulingResources,
) -> list[BaseConstraint]:
    """H1-H6, H9, H11, H12 -- exactly the constraints checked against every
    candidate before it's committed. H7/H8 are deliberately excluded; see
    this module's docstring."""
    return [
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


def _find_first_valid_candidate(
    lesson: LessonAssignment,
    state: SchedulingState,
    time_slot_ids: list[int],
    real_time_constraints: list[BaseConstraint],
    candidate_teacher_ids: list[int],
    candidate_room_ids: list[int | None],
) -> LessonAssignment | None:
    for teacher_id in candidate_teacher_ids:
        for time_slot_id in time_slot_ids:
            for room_id in candidate_room_ids:
                candidate = replace(
                    lesson,
                    teacher_id=teacher_id,
                    time_slot_id=time_slot_id,
                    room_id=room_id,
                )
                hypothetical = [*state.assignments, candidate]
                if all(c.validate(hypothetical) for c in real_time_constraints):
                    return candidate
    return None


def _explain_no_valid_candidate(
    lesson: LessonAssignment,
    state: SchedulingState,
    time_slot_ids: list[int],
    real_time_constraints: list[BaseConstraint],
    candidate_teacher_ids: list[int],
    candidate_room_ids: list[int | None],
) -> list[ConstraintViolation]:
    """Only called once a Lesson is already known to have no valid
    candidate. Re-tries every combination (the slow path -- fine, since it
    only runs on failure) and collects every distinct violation message
    across all of them, so the caller sees the full picture of why nothing
    worked rather than just the first failure. Deduplicated by message,
    since the same reason (e.g. "teacher X not qualified") would otherwise
    repeat once per time-slot/room combination tried with that teacher.
    """
    if not candidate_teacher_ids:
        return [
            ConstraintViolation(
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
                suggested_action=(
                    "Add a TeacherSubject qualification for this subject, "
                    "or check that the required-teacher rule (if any) "
                    "names an existing teacher."
                ),
            )
        ]

    seen_messages: set[str] = set()
    reasons: list[ConstraintViolation] = []
    for teacher_id in candidate_teacher_ids:
        for time_slot_id in time_slot_ids:
            for room_id in candidate_room_ids:
                candidate = replace(
                    lesson,
                    teacher_id=teacher_id,
                    time_slot_id=time_slot_id,
                    room_id=room_id,
                )
                hypothetical = [*state.assignments, candidate]
                for constraint in real_time_constraints:
                    for violation in constraint.explain_violations(hypothetical):
                        if violation.message in seen_messages:
                            continue
                        seen_messages.add(violation.message)
                        reasons.append(violation)
    return reasons


def schedule_greedy(
    lessons: list[LessonAssignment],
    resources: SchedulingResources,
    state: SchedulingState | None = None,
) -> GreedyResult:
    """Entry point.

    `lessons` is the to-do list: each one a LessonAssignment with
    teacher_id/time_slot_id/room_id all None (an unplaced lesson). Reusing
    LessonAssignment itself for "not yet assigned" rather than inventing a
    second, near-identical dataclass matches how a real Schedule row can
    already look before every part of it is filled in (see
    LessonAssignment's own docstring).

    `resources` bundles every other input the search needs (see
    SchedulingResources).

    `state` lets a caller seed the search with assignments that already
    exist (e.g. lessons placed by hand before running the algorithm);
    defaults to an empty SchedulingState.

    Returns a GreedyResult. On any failure, `state` is None -- see
    GreedyResult's docstring for the atomicity guarantee.
    """
    working_state = state if state is not None else SchedulingState()

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

    real_time_constraints = _build_real_time_constraints(resources)

    # MRV: process the Lesson with the fewest candidate teachers first.
    # A required teacher (H6) pins the candidate count to exactly 1, so
    # those Lessons always sort to the front.
    ordered_lessons = sorted(
        lessons,
        key=lambda lesson: len(
            _candidate_teacher_ids(
                lesson,
                required_teacher_by_requirement,
                qualified_teachers_by_subject,
            )
        ),
    )

    lesson_failures: list[LessonFailure] = []

    for lesson in ordered_lessons:
        candidate_teacher_ids = _candidate_teacher_ids(
            lesson, required_teacher_by_requirement, qualified_teachers_by_subject
        )
        candidate_room_ids = _candidate_room_ids(
            lesson, required_room_type_by_requirement, room_ids_by_type
        )

        candidate = _find_first_valid_candidate(
            lesson,
            working_state,
            resources.time_slot_ids,
            real_time_constraints,
            candidate_teacher_ids,
            candidate_room_ids,
        )

        if candidate is not None:
            working_state.add_assignment(candidate)
        else:
            reasons = _explain_no_valid_candidate(
                lesson,
                working_state,
                resources.time_slot_ids,
                real_time_constraints,
                candidate_teacher_ids,
                candidate_room_ids,
            )
            lesson_failures.append(
                LessonFailure(
                    lesson_id=lesson.lesson_id,
                    class_subject_requirement_id=lesson.class_subject_requirement_id,
                    reasons=reasons,
                )
            )

    if lesson_failures:
        return GreedyResult(
            success=False,
            state=None,
            lesson_failures=lesson_failures,
            post_hoc_violations=[],
        )

    # Every Lesson placed -- now the whole-batch H7/H8 checks (see module
    # docstring for why these run only here, once, at the end).
    weekly_periods_constraint = WeeklyPeriodsConstraint(resources.requirement_periods)
    workload_constraint = TeacherWorkloadConstraint(resources.teacher_workload_limits)
    post_hoc_violations = weekly_periods_constraint.explain_violations(
        working_state.assignments
    ) + workload_constraint.explain_violations(working_state.assignments)

    if post_hoc_violations:
        return GreedyResult(
            success=False,
            state=None,
            lesson_failures=[],
            post_hoc_violations=post_hoc_violations,
        )

    return GreedyResult(
        success=True,
        state=working_state,
        lesson_failures=[],
        post_hoc_violations=[],
    )
