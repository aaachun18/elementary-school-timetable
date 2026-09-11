"""Static feasibility checks run BEFORE any search begins (Task 23).

These three checks share a property that sets them apart from every
per-candidate Constraint in constraints/ and from the per-Lesson candidate
generation in algorithms/resources.py: each is an AGGREGATE, summed-up
comparison across a teacher's (or requirement's) ENTIRE batch of Lessons in
this run -- "does this teacher have enough weekly capacity/available time
slots for everything required of them", "is any involved entity simply
turned off" -- not a fact about one candidate or one Lesson in isolation.
None of them needs to try a single (teacher, time_slot, room) combination
to know the answer; a sum and a comparison settle it up front. Running a
full Backtracking search only to eventually discover one of these would be
strictly slower and no more informative than catching it here first, so
these run before schedule_backtracking()/schedule_greedy() are ever called
(see backend/app/services/scheduler.py::run_scheduler()).

Pure Python like everything else in scheduling_engine/ (see AGENTS.md
section 4): operates only on the same LessonAssignment/SchedulingResources
dataclasses already passed to the search algorithms -- no new inputs, no
DB access.
"""

from dataclasses import dataclass

from scheduling_engine.algorithms.resources import SchedulingResources
from scheduling_engine.constraints.base import ConstraintViolation, Severity
from scheduling_engine.models.domain import LessonAssignment


@dataclass
class StaticFeasibilityResult:
    """feasible=True: none of the three checks found anything, safe to
    proceed to a real search. feasible=False: violations lists EVERY
    problem found across all three checks (not just the first), same
    "report everything, don't stop at the first failure" stance the rest
    of the engine's diagnostics already take (see GreedyResult's
    lesson_failures)."""

    feasible: bool
    violations: list[ConstraintViolation]


def _lesson_counts_by_required_teacher(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> dict[int, tuple[int, list[int]]]:
    """teacher_id -> (total Lesson count pinned to them via a
    required_teacher_id rule, sorted distinct class_subject_requirement_ids
    contributing to that count). Shared by the two teacher-capacity checks
    below, which both need exactly this breakdown."""
    required_teacher_by_requirement = {
        rule.class_subject_requirement_id: rule.required_teacher_id
        for rule in resources.required_teacher_rules
    }
    counts: dict[int, int] = {}
    requirement_ids: dict[int, set[int]] = {}
    for lesson in lessons:
        teacher_id = required_teacher_by_requirement.get(
            lesson.class_subject_requirement_id
        )
        if teacher_id is None:
            continue
        counts[teacher_id] = counts.get(teacher_id, 0) + 1
        requirement_ids.setdefault(teacher_id, set()).add(
            lesson.class_subject_requirement_id
        )
    return {
        teacher_id: (count, sorted(requirement_ids[teacher_id]))
        for teacher_id, count in counts.items()
    }


def _check_teacher_workload_exceeded(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> list[ConstraintViolation]:
    """A teacher pinned (via required_teacher_id) to more Lessons in this
    run than their max_weekly_periods allows can never be scheduled, no
    matter which time slots/rooms are tried for the rest of the batch --
    every one of those Lessons MUST use this exact teacher, so the sum
    alone is a hard lower bound on their final workload."""
    max_periods_by_teacher = {
        limit.teacher_id: limit.max_weekly_periods
        for limit in resources.teacher_workload_limits
    }

    violations: list[ConstraintViolation] = []
    for teacher_id, (
        required_count,
        requirement_ids,
    ) in _lesson_counts_by_required_teacher(lessons, resources).items():
        max_periods = max_periods_by_teacher.get(teacher_id)
        if max_periods is None or required_count <= max_periods:
            continue
        violations.append(
            ConstraintViolation(
                type="STATIC_TEACHER_WORKLOAD_EXCEEDED",
                severity=Severity.ERROR,
                lesson_id=None,
                teacher_id=teacher_id,
                class_id=None,
                subject_id=None,
                time_slot_id=None,
                message=(
                    f"Teacher {teacher_id} is required (via required_teacher_id) "
                    f"for {required_count} lessons this run -- across "
                    f"requirement(s) {requirement_ids} -- but their "
                    f"max_weekly_periods is only {max_periods}."
                ),
                suggested_action=(
                    f"Raise teacher {teacher_id}'s max_weekly_periods, reduce "
                    "weekly_periods on the affected requirement(s), or "
                    "reassign the required-teacher rule on some of them."
                ),
            )
        )
    return violations


def _check_teacher_availability_insufficient(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> list[ConstraintViolation]:
    """A teacher pinned to more Lessons than they have available time slots
    for (all school time slots minus that teacher's TeacherAvailability
    unavailable-slot rows) can never fit them all in -- again a pure count
    comparison, independent of which slots any other Lesson ends up
    using."""
    total_slots = len(resources.time_slot_ids)
    unavailable_count_by_teacher: dict[int, int] = {}
    for unavailability in resources.teacher_unavailability:
        unavailable_count_by_teacher[unavailability.teacher_id] = (
            unavailable_count_by_teacher.get(unavailability.teacher_id, 0) + 1
        )

    violations: list[ConstraintViolation] = []
    for teacher_id, (
        required_count,
        requirement_ids,
    ) in _lesson_counts_by_required_teacher(lessons, resources).items():
        available_slots = total_slots - unavailable_count_by_teacher.get(
            teacher_id, 0
        )
        if required_count <= available_slots:
            continue
        violations.append(
            ConstraintViolation(
                type="STATIC_TEACHER_AVAILABILITY_INSUFFICIENT",
                severity=Severity.ERROR,
                lesson_id=None,
                teacher_id=teacher_id,
                class_id=None,
                subject_id=None,
                time_slot_id=None,
                message=(
                    f"Teacher {teacher_id} is required (via required_teacher_id) "
                    f"for {required_count} lessons this run -- across "
                    f"requirement(s) {requirement_ids} -- but only has "
                    f"{available_slots} available time slot(s) "
                    f"({total_slots} total school time slots - "
                    f"{unavailable_count_by_teacher.get(teacher_id, 0)} marked "
                    "unavailable for this teacher)."
                ),
                suggested_action=(
                    f"Remove some of teacher {teacher_id}'s unavailable time "
                    "slots, reduce weekly_periods on the affected "
                    "requirement(s), or reassign the required-teacher rule "
                    "on some of them."
                ),
            )
        )
    return violations


def _check_inactive_entity_conflict(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> list[ConstraintViolation]:
    """For every requirement with at least one Lesson in this run, its
    class, its subject, and (if set) its required_teacher must all be
    active. An inactive entity can never be validly scheduled (H12), and
    unlike the two checks above this needs no aggregate math at all -- one
    is_active lookup per entity per requirement settles it, independent of
    every other Lesson in the batch.

    Mirrors ActiveStatusConstraint's own convention (constraints/active_
    status.py): only entities explicitly recorded as inactive are flagged;
    an id with no matching ActiveStatusInfo at all is treated as active
    rather than guessed at.
    """
    inactive: set[tuple[str, int]] = {
        (info.entity_type, info.entity_id)
        for info in resources.active_statuses
        if not info.is_active
    }
    required_teacher_by_requirement = {
        rule.class_subject_requirement_id: rule.required_teacher_id
        for rule in resources.required_teacher_rules
    }

    violations: list[ConstraintViolation] = []
    seen_requirement_ids: set[int] = set()
    for lesson in lessons:
        requirement_id = lesson.class_subject_requirement_id
        if requirement_id in seen_requirement_ids:
            continue
        seen_requirement_ids.add(requirement_id)

        if ("class", lesson.class_id) in inactive:
            violations.append(
                ConstraintViolation(
                    type="STATIC_INACTIVE_ENTITY_CONFLICT",
                    severity=Severity.ERROR,
                    lesson_id=None,
                    teacher_id=None,
                    class_id=lesson.class_id,
                    subject_id=None,
                    time_slot_id=None,
                    class_subject_requirement_id=requirement_id,
                    message=(
                        f"Requirement {requirement_id}'s class {lesson.class_id} "
                        "is inactive (is_active=False)."
                    ),
                    suggested_action=(
                        f"Reactivate class {lesson.class_id}, or remove/"
                        "postpone this requirement."
                    ),
                )
            )

        if ("subject", lesson.subject_id) in inactive:
            violations.append(
                ConstraintViolation(
                    type="STATIC_INACTIVE_ENTITY_CONFLICT",
                    severity=Severity.ERROR,
                    lesson_id=None,
                    teacher_id=None,
                    class_id=None,
                    subject_id=lesson.subject_id,
                    time_slot_id=None,
                    class_subject_requirement_id=requirement_id,
                    message=(
                        f"Requirement {requirement_id}'s subject "
                        f"{lesson.subject_id} is inactive (is_active=False)."
                    ),
                    suggested_action=(
                        f"Reactivate subject {lesson.subject_id}, or remove/"
                        "postpone this requirement."
                    ),
                )
            )

        required_teacher_id = required_teacher_by_requirement.get(requirement_id)
        if required_teacher_id is not None and (
            "teacher",
            required_teacher_id,
        ) in inactive:
            violations.append(
                ConstraintViolation(
                    type="STATIC_INACTIVE_ENTITY_CONFLICT",
                    severity=Severity.ERROR,
                    lesson_id=None,
                    teacher_id=required_teacher_id,
                    class_id=None,
                    subject_id=None,
                    time_slot_id=None,
                    class_subject_requirement_id=requirement_id,
                    message=(
                        f"Requirement {requirement_id}'s required teacher "
                        f"{required_teacher_id} is inactive (is_active=False)."
                    ),
                    suggested_action=(
                        f"Reactivate teacher {required_teacher_id}, or "
                        "change/remove the required-teacher rule on this "
                        "requirement."
                    ),
                )
            )

    return violations


def check_static_feasibility(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> StaticFeasibilityResult:
    """Entry point: run all three checks and combine their results.

    Only required_teacher_id is checked for capacity/availability -- a
    Lesson with no required-teacher rule is free to use ANY qualified
    teacher, so there's no single teacher whose personal capacity/
    availability can be blamed in advance; that case can only be
    (correctly) discovered by the search itself, exactly as it already is.
    """
    violations = (
        _check_teacher_workload_exceeded(lessons, resources)
        + _check_teacher_availability_insufficient(lessons, resources)
        + _check_inactive_entity_conflict(lessons, resources)
    )
    return StaticFeasibilityResult(feasible=not violations, violations=violations)
