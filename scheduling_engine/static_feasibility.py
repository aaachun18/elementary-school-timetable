"""Static feasibility checks run BEFORE any search begins (Task 23; the 4th
check below added by the Task 38 bug fix, the 5th -- fixed time slots -- by
Task 81).

All five checks share a property that sets them apart from every
per-candidate Constraint in constraints/: each is a fact checkable up front,
without trying a single (teacher, time_slot, room) combination --
"does this teacher have enough weekly capacity/available time slots for
everything required of them", "is any involved entity simply turned off",
"does this Lesson have any candidate teacher AT ALL". Running a full
Backtracking search only to eventually discover one of these would be
strictly slower and no more informative than catching it here first, so
these run before schedule_backtracking()/schedule_greedy() are ever called
(see backend/app/services/scheduler.py::run_scheduler()).

Task 38 bug fix: a real run combining a STATIC_TEACHER_WORKLOAD_EXCEEDED
problem with a separate "no qualified teacher at all" problem (for a
different Lesson) only ever reported the workload one. Root cause:
run_scheduler() returns immediately when check_static_feasibility() finds
anything, WITHOUT ever calling schedule_backtracking() -- and "zero
candidate teachers" used to be checked ONLY inside schedule_backtracking()'s
own pre-flight step (still is, unchanged, for callers that invoke it
directly/its own tests), so it never got a chance to run at all whenever a
static check failed first. The fix is not to remove that short-circuit --
running a full search once we already know from a cheap aggregate check that
success is impossible would be pure waste -- but to make the SAME kind of
cheap, no-search aggregate check catch this case too, here, alongside the
other three, so check_static_feasibility() is a genuinely complete
"everything checkable without searching" pass and nothing checkable that way
depends on which check happens to run first.

Pure Python like everything else in scheduling_engine/ (see AGENTS.md
section 4): operates only on the same LessonAssignment/SchedulingResources
dataclasses already passed to the search algorithms -- no new inputs, no
DB access.
"""

from dataclasses import dataclass, replace

from scheduling_engine.algorithms.blocks import (
    SchedulingUnit,
    build_units,
    teaching_runs,
    unit_windows,
    weekday_by_slot,
)
from scheduling_engine.algorithms.resources import (
    LessonFailure,
    LookupTables,
    SchedulingResources,
    build_lookup_tables,
    candidate_teacher_ids,
    no_candidate_teacher_violation,
)
from scheduling_engine.constraints.base import ConstraintViolation, Severity
from scheduling_engine.models.domain import LessonAssignment


@dataclass
class StaticFeasibilityResult:
    """feasible=True: none of the five checks found anything, safe to
    proceed to a real search. feasible=False: violations/lesson_failures
    together list EVERY problem found across all five checks (not just the
    first), same "report everything, don't stop at the first failure"
    stance the rest of the engine's diagnostics already take (see
    GreedyResult's lesson_failures).

    Split into two lists, not one, for the same reason BacktrackingResult
    and GreedyResult already split lesson_failures from post_hoc_violations:
    violations are facts about the batch's settings (teacher workload/
    availability, inactive entities, and -- Task 81 -- fixed time slots,
    which do name their Lesson, class, subject and slot), while
    lesson_failures are about one SPECIFIC Lesson that can never be placed
    (zero candidate teachers) -- collapsing the two into one undifferentiated
    list would lose that distinction for every caller downstream (e.g.
    FailureDiagnostics.tsx's per-lesson vs whole-batch sections).
    """

    feasible: bool
    violations: list[ConstraintViolation]
    lesson_failures: list[LessonFailure]


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
    default_room_by_requirement = {
        item.class_subject_requirement_id: item.room_id for item in resources.default_rooms
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

        # Task 92B: the homeroom is the lesson's only room candidate, so an
        # inactive one can never be used (H12) -- same kind of fact.
        default_room_id = default_room_by_requirement.get(requirement_id)
        if default_room_id is not None and ("room", default_room_id) in inactive:
            violations.append(
                ConstraintViolation(
                    type="STATIC_INACTIVE_ENTITY_CONFLICT",
                    severity=Severity.ERROR,
                    lesson_id=None,
                    teacher_id=None,
                    class_id=None,
                    subject_id=None,
                    time_slot_id=None,
                    room_id=default_room_id,
                    class_subject_requirement_id=requirement_id,
                    message=(
                        f"Requirement {requirement_id}'s homeroom {default_room_id} "
                        "is inactive (is_active=False)."
                    ),
                    suggested_action=(
                        f"Reactivate room {default_room_id}, or change the class's "
                        "homeroom."
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


def _check_zero_candidate_teacher_lessons(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> list[LessonFailure]:
    """A Lesson with zero candidate teachers at all -- no teacher holds the
    H5 qualification for its subject (or the one H6 required_teacher_id
    names does, but lacks it) -- can never be placed no matter what the
    search tries, independent of every other Lesson in the batch: exactly
    the same "aggregate, no-search-needed fact" property as the three checks
    above.

    Reuses build_lookup_tables()/candidate_teacher_ids()/
    no_candidate_teacher_violation() from algorithms/resources.py --
    verbatim the same functions schedule_backtracking()'s own pre-flight
    step uses (see backtracking.py's trivial_failures) -- so "zero
    candidates" is decided in exactly one place. This does NOT replace that
    pre-flight step: schedule_backtracking() stays fully self-contained
    (still correct, still tested, when called directly rather than through
    run_scheduler()); this just means run_scheduler() no longer has to reach
    the search at all to already know the answer for this case.
    """
    tables = build_lookup_tables(resources)
    return [
        LessonFailure(
            lesson_id=lesson.lesson_id,
            class_subject_requirement_id=lesson.class_subject_requirement_id,
            reasons=[no_candidate_teacher_violation(lesson, tables)],
        )
        for lesson in lessons
        if not candidate_teacher_ids(lesson, tables)
    ]


# --- Task 81: fixed time slots ---
#
# A Lesson fixed to a time slot (Lesson.fixed_time_slot_id) reaches the
# engine as a pending LessonAssignment whose time_slot_id is already set;
# candidate_time_slot_ids() makes that slot its ONLY time candidate (Task
# 28), so the search can never place it anywhere else. What the search
# could not do is say clearly, up front, that a fixed slot can never work:
# such a run used to end as an anonymous DEFINITELY_INFEASIBLE after a full
# Backtracking search. Every check below is decidable from the fixed slots
# alone, without trying a single combination -- the same property as the
# other checks in this module.

FIXED_SLOT_UNKNOWN = "STATIC_FIXED_SLOT_UNKNOWN"
FIXED_SLOT_NON_TEACHING = "STATIC_FIXED_SLOT_NON_TEACHING"
FIXED_SLOT_TEACHER_UNAVAILABLE = "STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE"
FIXED_SLOT_CLASS_CLASH = "STATIC_FIXED_SLOT_CLASS_CLASH"
FIXED_SLOT_TEACHER_CLASH = "STATIC_FIXED_SLOT_TEACHER_CLASH"
FIXED_SLOT_ROOM_SHORTAGE = "STATIC_FIXED_SLOT_ROOM_SHORTAGE"
FIXED_SLOT_HOMEROOM_CLASH = "STATIC_FIXED_SLOT_HOMEROOM_CLASH"


def _fixed_slot_violation(
    violation_type: str,
    lesson: LessonAssignment,
    message: str,
    suggested_action: str,
    *,
    teacher_id: int | None = None,
) -> ConstraintViolation:
    """Every fixed-slot problem names the Lesson it is about -- its class,
    subject and the fixed time slot -- so the console can say which course
    and which slot."""
    return ConstraintViolation(
        type=violation_type,
        severity=Severity.ERROR,
        lesson_id=lesson.lesson_id,
        teacher_id=teacher_id,
        class_id=lesson.class_id,
        subject_id=lesson.subject_id,
        time_slot_id=lesson.time_slot_id,
        class_subject_requirement_id=lesson.class_subject_requirement_id,
        message=message,
        suggested_action=suggested_action,
    )


def _check_fixed_time_slots(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> list[ConstraintViolation]:
    """Fixed time slots that can never be honored:

    - the slot is not one of the school's time slots at all (UNKNOWN);
    - the slot is a non-teaching period, so H11 rejects it (NON_TEACHING);
    - every teacher who could teach the lesson -- the required teacher, or
      every qualified teacher when none is required -- is marked
      unavailable at that slot, so H4 rejects every candidate
      (TEACHER_UNAVAILABLE);
    - two or more Lessons of the same class are fixed to the same slot, an
      unavoidable H2 (CLASS_CLASH);
    - two or more Lessons fixed to the same slot can only be taught by the
      same one teacher (a required teacher, or the subject's only qualified
      teacher), an unavoidable H1 (TEACHER_CLASH);
    - more Lessons needing a room type are fixed to one slot than there
      are rooms of that type, an unavoidable H3/H9 (ROOM_SHORTAGE);
    - Task 92B: Lessons of two or more classes sharing one homeroom are
      fixed to the same slot -- the homeroom is their only room, an
      unavoidable H3 (HOMEROOM_CLASH). Lessons of one class alone are
      already CLASS_CLASH.

    The clash checks report every Lesson involved, not just the second
    one. Lessons without a fixed slot are skipped entirely, so a run with
    no fixed slots does nothing here beyond one pass over the list. A
    Lesson with no candidate teacher at all is left to
    _check_zero_candidate_teacher_lessons().
    """
    fixed = [lesson for lesson in lessons if lesson.time_slot_id is not None]
    if not fixed:
        return []

    tables = build_lookup_tables(resources)
    known_slots = set(resources.time_slot_ids)
    teaching_by_slot = {
        slot.time_slot_id: slot.is_teaching_period for slot in resources.time_slots
    }
    unavailable = {
        (item.teacher_id, item.time_slot_id) for item in resources.teacher_unavailability
    }

    violations: list[ConstraintViolation] = []
    placeable: list[LessonAssignment] = []
    for lesson in fixed:
        slot_id = lesson.time_slot_id
        assert slot_id is not None
        if slot_id not in known_slots:
            violations.append(
                _fixed_slot_violation(
                    FIXED_SLOT_UNKNOWN,
                    lesson,
                    f"Lesson {lesson.lesson_id} is fixed to time slot {slot_id}, "
                    "which is not one of the school's time slots.",
                    "Fix this lesson to an existing teaching time slot, or clear "
                    "its fixed time slot.",
                )
            )
            continue
        # Same "unknown -> not a violation" stance as H11 itself: a slot
        # with no TimeSlotInfo is treated as a teaching period.
        if teaching_by_slot.get(slot_id) is False:
            violations.append(
                _fixed_slot_violation(
                    FIXED_SLOT_NON_TEACHING,
                    lesson,
                    f"Lesson {lesson.lesson_id} is fixed to time slot {slot_id}, "
                    "which is a non-teaching period.",
                    "Fix this lesson to a teaching time slot, or clear its fixed "
                    "time slot.",
                )
            )
            continue
        placeable.append(lesson)

        candidates = candidate_teacher_ids(lesson, tables)
        if candidates and all((teacher, slot_id) in unavailable for teacher in candidates):
            only_teacher = candidates[0] if len(candidates) == 1 else None
            violations.append(
                _fixed_slot_violation(
                    FIXED_SLOT_TEACHER_UNAVAILABLE,
                    lesson,
                    f"Lesson {lesson.lesson_id} is fixed to time slot {slot_id}, "
                    f"but every teacher who can teach it ({candidates}) is marked "
                    "unavailable then.",
                    "Fix this lesson to another time slot, or remove the "
                    "teacher's unavailable time slot.",
                    teacher_id=only_teacher,
                )
            )

    violations.extend(_fixed_slot_clashes(placeable, tables))
    return violations


def _fixed_slot_clashes(
    fixed: list[LessonAssignment], tables: LookupTables
) -> list[ConstraintViolation]:
    by_class_slot: dict[tuple[int, int | None], list[LessonAssignment]] = {}
    by_teacher_slot: dict[tuple[int, int | None], list[LessonAssignment]] = {}
    by_room_type_slot: dict[tuple[str, int | None], list[LessonAssignment]] = {}
    by_homeroom_slot: dict[tuple[int, int | None], list[LessonAssignment]] = {}
    for lesson in fixed:
        by_class_slot.setdefault((lesson.class_id, lesson.time_slot_id), []).append(lesson)
        candidates = candidate_teacher_ids(lesson, tables)
        if len(candidates) == 1:
            by_teacher_slot.setdefault((candidates[0], lesson.time_slot_id), []).append(lesson)
        room_type = tables.required_room_type_by_requirement.get(
            lesson.class_subject_requirement_id
        )
        if room_type is not None:
            by_room_type_slot.setdefault((room_type, lesson.time_slot_id), []).append(lesson)
        else:
            homeroom = tables.default_room_by_requirement.get(lesson.class_subject_requirement_id)
            if homeroom is not None:
                by_homeroom_slot.setdefault((homeroom, lesson.time_slot_id), []).append(lesson)

    violations: list[ConstraintViolation] = []
    for (class_id, slot_id), group in by_class_slot.items():
        if len(group) < 2:
            continue
        lesson_ids = [lesson.lesson_id for lesson in group]
        for lesson in group:
            violations.append(
                _fixed_slot_violation(
                    FIXED_SLOT_CLASS_CLASH,
                    lesson,
                    f"Lessons {lesson_ids} of class {class_id} are all fixed to "
                    f"time slot {slot_id}.",
                    "Fix only one of these lessons to this time slot.",
                )
            )
    for (teacher_id, slot_id), group in by_teacher_slot.items():
        if len(group) < 2:
            continue
        lesson_ids = [lesson.lesson_id for lesson in group]
        for lesson in group:
            violations.append(
                _fixed_slot_violation(
                    FIXED_SLOT_TEACHER_CLASH,
                    lesson,
                    f"Lessons {lesson_ids} are all fixed to time slot {slot_id} "
                    f"and can only be taught by teacher {teacher_id}.",
                    "Fix only one of these lessons to this time slot, or let "
                    "another teacher teach one of them.",
                    teacher_id=teacher_id,
                )
            )
    for (room_type, slot_id), group in by_room_type_slot.items():
        room_count = len(tables.room_ids_by_type.get(room_type, []))
        if len(group) <= room_count:
            continue
        lesson_ids = [lesson.lesson_id for lesson in group]
        for lesson in group:
            violations.append(
                _fixed_slot_violation(
                    FIXED_SLOT_ROOM_SHORTAGE,
                    lesson,
                    f"Lessons {lesson_ids} are all fixed to time slot {slot_id} "
                    f"and need a room of type '{room_type}', but only "
                    f"{room_count} such room(s) exist.",
                    "Fix fewer of these lessons to this time slot, or add rooms "
                    "of this type.",
                )
            )
    for (room_id, slot_id), group in by_homeroom_slot.items():
        class_ids = sorted({lesson.class_id for lesson in group})
        if len(class_ids) < 2:
            continue
        lesson_ids = [lesson.lesson_id for lesson in group]
        for lesson in group:
            violation = _fixed_slot_violation(
                FIXED_SLOT_HOMEROOM_CLASH,
                lesson,
                f"班級 {_join(class_ids)} 共用導師教室 {room_id}，而課程 {_join(lesson_ids)} 都固定在時段 "
                f"{slot_id}，這間教室同一時段只能上一堂課",
                "只把其中一堂課固定在這個時段，或替其中一班改設導師教室",
            )
            violations.append(replace(violation, room_id=room_id))
    return violations


# --- Task 87: lesson blocks (連堂) ---
#
# A block needs `size` consecutive teaching periods on one day, the blocks
# of one requirement need different days, and fixed lessons inside a block
# pin where it starts. Each check below is decidable from the time slots,
# the blocks and the fixed slots alone -- no search.

BLOCK_TOO_LONG = "STATIC_BLOCK_TOO_LONG"
BLOCK_TOO_MANY_DAYS = "STATIC_BLOCK_TOO_MANY_DAYS"
BLOCK_NOT_ENOUGH_DAYS = "STATIC_BLOCK_NOT_ENOUGH_DAYS"
BLOCK_FIXED_CONFLICT = "STATIC_BLOCK_FIXED_CONFLICT"
BLOCK_FIXED_SAME_DAY = "STATIC_BLOCK_FIXED_SAME_DAY"
BLOCK_TEACHER_UNAVAILABLE = "STATIC_BLOCK_TEACHER_UNAVAILABLE"


def _block_violation(
    violation_type: str,
    unit: SchedulingUnit,
    message: str,
    suggested_action: str,
    *,
    teacher_id: int | None = None,
) -> ConstraintViolation:
    """Names the requirement (class, subject) and, through lesson_id, the
    block's first lesson."""
    first = unit.lessons[0]
    return ConstraintViolation(
        type=violation_type,
        severity=Severity.ERROR,
        lesson_id=first.lesson_id,
        teacher_id=teacher_id,
        class_id=first.class_id,
        subject_id=first.subject_id,
        time_slot_id=None,
        class_subject_requirement_id=first.class_subject_requirement_id,
        message=message,
        suggested_action=suggested_action,
    )


def _check_lesson_blocks(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> list[ConstraintViolation]:
    """Blocks that can never be placed:

    - a block longer than the longest run of consecutive teaching periods
      on any day (TOO_LONG);
    - more blocks in one requirement than days with a teaching period
      (TOO_MANY_DAYS);
    - not enough DIFFERENT days with a long enough run for all of a
      requirement's blocks at once, e.g. "3+3" when only one day has three
      consecutive teaching periods (NOT_ENOUGH_DAYS);
    - fixed lessons inside one block that contradict each other or the
      consecutive periods -- different days, not adjacent, out of block
      order, or past the end of a run (FIXED_CONFLICT);
    - two blocks of one requirement fixed to the same day (FIXED_SAME_DAY);
    - every teacher who can teach the block has an unavailable period in
      every window the block could use (TEACHER_UNAVAILABLE).

    Fixed slots that are unknown or non-teaching are left to
    _check_fixed_time_slots(). Lessons in no block are skipped, so without
    blocks this does nothing.
    """
    if not resources.lesson_blocks:
        return []
    units = [unit for unit in build_units(lessons, resources) if unit.block is not None]
    if not units:
        return []

    tables = build_lookup_tables(resources)
    runs = teaching_runs(resources)
    weekday_of = weekday_by_slot(resources)
    longest_run_by_day: dict[int, int] = {}
    for run in runs:
        weekday = weekday_of[run[0]]
        longest_run_by_day[weekday] = max(longest_run_by_day.get(weekday, 0), len(run))
    longest_run = max(longest_run_by_day.values(), default=0)
    teaching_slots = {slot_id for run in runs for slot_id in run}
    unavailable = {(item.teacher_id, item.time_slot_id) for item in resources.teacher_unavailability}

    violations: list[ConstraintViolation] = []
    units_by_requirement: dict[int, list[SchedulingUnit]] = {}
    for unit in units:
        units_by_requirement.setdefault(unit.lessons[0].class_subject_requirement_id, []).append(unit)

    for requirement_id, requirement_units in units_by_requirement.items():
        sizes = sorted((len(unit.lessons) for unit in requirement_units), reverse=True)
        any_too_long = False
        for unit in requirement_units:
            size = len(unit.lessons)
            if size > longest_run:
                any_too_long = True
                violations.append(
                    _block_violation(
                        BLOCK_TOO_LONG,
                        unit,
                        f"Block {unit.block.block_no} of requirement {requirement_id} needs "  # type: ignore[union-attr]
                        f"{size} consecutive teaching periods, but no day has more than {longest_run}.",
                        "Use smaller blocks in the lesson pattern, or add teaching periods.",
                    )
                )
        days = len(longest_run_by_day)
        if len(requirement_units) > days:
            violations.append(
                _block_violation(
                    BLOCK_TOO_MANY_DAYS,
                    requirement_units[0],
                    f"Requirement {requirement_id} has {len(requirement_units)} blocks, which must "
                    f"be on different days, but the school has only {days} day(s) with teaching periods.",
                    "Use fewer blocks in the lesson pattern.",
                )
            )
        elif not any_too_long:
            # Blocks largest first against days with the longest runs first:
            # each block needs its own day with a long enough run.
            day_lengths = sorted(longest_run_by_day.values(), reverse=True)
            if any(day_lengths[index] < size for index, size in enumerate(sizes)):
                violations.append(
                    _block_violation(
                        BLOCK_NOT_ENOUGH_DAYS,
                        requirement_units[0],
                        f"Requirement {requirement_id}'s blocks {sizes} each need their own day with "
                        f"that many consecutive teaching periods; the days only have runs of {day_lengths}.",
                        "Use smaller blocks in the lesson pattern, or add teaching periods.",
                    )
                )

        fixed_days: dict[int, list[int]] = {}
        for unit in requirement_units:
            block_no = unit.block.block_no  # type: ignore[union-attr]
            fixed = [
                lesson.time_slot_id
                for lesson in unit.lessons
                if lesson.time_slot_id is not None
            ]
            if fixed and all(slot_id in teaching_slots for slot_id in fixed):
                windows = unit_windows(unit, resources)
                if not windows:
                    violations.append(
                        _block_violation(
                            BLOCK_FIXED_CONFLICT,
                            unit,
                            f"The fixed time slots {fixed} of block {block_no} of requirement "
                            f"{requirement_id} can't all be inside one run of {len(unit.lessons)} "
                            "consecutive teaching periods in block order.",
                            "Fix the block's lessons to consecutive teaching periods of one day, "
                            "in order, or clear their fixed time slots.",
                        )
                    )
                    continue
                window_days = {weekday_of[window[0]] for window in windows}
                if len(window_days) == 1:
                    fixed_days.setdefault(next(iter(window_days)), []).append(block_no)

            candidates = candidate_teacher_ids(unit.lessons[0], tables)
            windows = unit_windows(unit, resources)
            if (
                candidates
                and windows
                and all(
                    any((teacher_id, slot_id) in unavailable for slot_id in window)
                    for teacher_id in candidates
                    for window in windows
                )
            ):
                violations.append(
                    _block_violation(
                        BLOCK_TEACHER_UNAVAILABLE,
                        unit,
                        f"Every teacher who can teach block {block_no} of requirement {requirement_id} "
                        f"({candidates}) is unavailable in some period of every window of "
                        f"{len(unit.lessons)} consecutive teaching periods it could use.",
                        "Remove some of the teacher's unavailable time slots, or change the lesson pattern.",
                        teacher_id=candidates[0] if len(candidates) == 1 else None,
                    )
                )

        for weekday, block_nos in fixed_days.items():
            if len(block_nos) < 2:
                continue
            for unit in requirement_units:
                if unit.block.block_no in block_nos:  # type: ignore[union-attr]
                    violations.append(
                        _block_violation(
                            BLOCK_FIXED_SAME_DAY,
                            unit,
                            f"Blocks {sorted(block_nos)} of requirement {requirement_id} are fixed "
                            f"to the same day (weekday {weekday}); its blocks must be on different days.",
                            "Fix the blocks to different days, or clear their fixed time slots.",
                        )
                    )
    return violations


# --- Task 92B: rooms ---


def _join(ids: list[int]) -> str:
    return "、".join(str(item) for item in ids)

ROOM_TYPE_NOT_FOUND = "STATIC_ROOM_TYPE_NOT_FOUND"
HOMEROOM_OVERBOOKED = "STATIC_HOMEROOM_OVERBOOKED"


def _teaching_slot_count(resources: SchedulingResources) -> int:
    """Same "unknown -> teaching" stance as H11: a slot without
    TimeSlotInfo counts as a teaching period."""
    non_teaching = {
        slot.time_slot_id for slot in resources.time_slots if not slot.is_teaching_period
    }
    return len(set(resources.time_slot_ids) - non_teaching)


def _check_rooms(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> list[ConstraintViolation]:
    """Rooms that can never be enough, decidable without searching:

    - a requirement's room type matches no active room at all -- the type
      is compared as the exact same string (RoomTypeConstraint, H9), so
      e.g. "自然教室" and "自然教室 " are different types
      (ROOM_TYPE_NOT_FOUND, once per requirement);
    - a homeroom is the only room of more lessons than there are teaching
      periods in the week -- typically two classes sharing one homeroom
      (HOMEROOM_OVERBOOKED, once per room).

    The messages are the user-facing text (Traditional Chinese): the
    frontend has no sentence of its own for these types yet.
    """
    tables = build_lookup_tables(resources)
    inactive_rooms = {
        info.entity_id
        for info in resources.active_statuses
        if info.entity_type == "room" and not info.is_active
    }
    violations: list[ConstraintViolation] = []

    seen_requirement_ids: set[int] = set()
    for lesson in lessons:
        requirement_id = lesson.class_subject_requirement_id
        room_type = tables.required_room_type_by_requirement.get(requirement_id)
        if room_type is None or requirement_id in seen_requirement_ids:
            continue
        seen_requirement_ids.add(requirement_id)
        if any(
            room_id not in inactive_rooms for room_id in tables.room_ids_by_type.get(room_type, [])
        ):
            continue
        violations.append(
            ConstraintViolation(
                type=ROOM_TYPE_NOT_FOUND,
                severity=Severity.ERROR,
                lesson_id=None,
                teacher_id=None,
                class_id=lesson.class_id,
                subject_id=lesson.subject_id,
                time_slot_id=None,
                class_subject_requirement_id=requirement_id,
                message=(
                    f"需求 {requirement_id}（班級 {lesson.class_id}、科目 {lesson.subject_id}）"
                    f"指定的教室類型「{room_type}」找不到任何可用的教室"
                ),
                suggested_action=(
                    "新增這個類型的教室，或把需求的教室類型改成與教室資料完全相同的名稱"
                ),
            )
        )

    teaching_slots = _teaching_slot_count(resources)
    by_homeroom: dict[int, list[LessonAssignment]] = {}
    for lesson in lessons:
        if lesson.class_subject_requirement_id in tables.required_room_type_by_requirement:
            continue
        homeroom = tables.default_room_by_requirement.get(lesson.class_subject_requirement_id)
        if homeroom is not None:
            by_homeroom.setdefault(homeroom, []).append(lesson)
    for room_id, group in by_homeroom.items():
        if len(group) <= teaching_slots:
            continue
        class_ids = sorted({lesson.class_id for lesson in group})
        violations.append(
            ConstraintViolation(
                type=HOMEROOM_OVERBOOKED,
                severity=Severity.ERROR,
                lesson_id=None,
                teacher_id=None,
                class_id=class_ids[0] if len(class_ids) == 1 else None,
                subject_id=None,
                time_slot_id=None,
                room_id=room_id,
                message=(
                    f"導師教室 {room_id} 要上 {len(group)} 堂課，"
                    f"但一週只有 {teaching_slots} 個教學時段（班級 {_join(class_ids)}）"
                ),
                suggested_action="替共用這間教室的班級改設不同的導師教室",
            )
        )
    return violations


def check_static_feasibility(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> StaticFeasibilityResult:
    """Entry point: run all seven checks (the fixed-time-slot check added
    in Task 81, the lesson-block check in Task 87, the room check in Task
    92B) and combine their results -- see
    this module's docstring for why all of them must run together rather than
    stopping at the first one that finds something (the Task 38 bug this
    fixed was exactly that: a real run with both a workload problem and a
    zero-candidate-teacher problem only ever reported the workload one).

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
        + _check_fixed_time_slots(lessons, resources)
        + _check_lesson_blocks(lessons, resources)
        + _check_rooms(lessons, resources)
    )
    lesson_failures = _check_zero_candidate_teacher_lessons(lessons, resources)
    return StaticFeasibilityResult(
        feasible=not violations and not lesson_failures,
        violations=violations,
        lesson_failures=lesson_failures,
    )
