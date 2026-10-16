"""Task 61: read-only "check an existing timetable". Converts a saved
ScheduleVersion's Schedule rows into scheduling_engine LessonAssignments and
runs every existing Hard Constraint's explain_violations() over them.

Unlike run_scheduler(), this never searches and never writes: it only
reports what is wrong with the timetable as it currently stands (DRAFT or
PUBLISHED). Task 88: it also checks lesson blocks (連堂, the engine's own
LessonBlockConstraint) and reports a teacher below their minimum weekly
periods as a WARNING (TEACHER_MIN_WORKLOAD) -- the only non-ERROR type.
Nothing here commits, adds, or modifies any row -- it is the
validation step later features (copy to next semester, reassigning a
teacher, manual edits) can call after the fact.
"""

from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

# Must be imported before anything from scheduling_engine: importing
# app.services.scheduler runs its sys.path bootstrap, which is what makes
# the repo-root scheduling_engine package importable when the app runs
# with backend/ as the working directory (see that module's comment).
from app.services.scheduler import (
    build_lesson_blocks,
    build_scheduling_resources,
    load_semester_requirements,
)

from scheduling_engine.algorithms.blocks import block_constraints  # noqa: E402
from scheduling_engine.algorithms.resources import (  # noqa: E402
    SchedulingResources,
    build_real_time_constraints,
)
from scheduling_engine.constraints.base import (  # noqa: E402
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.constraints.teacher_min_workload import (  # noqa: E402
    TeacherMinWorkloadConstraint,
)
from scheduling_engine.constraints.weekly_periods import (  # noqa: E402
    WeeklyPeriodsConstraint,
)
from scheduling_engine.models.domain import (  # noqa: E402
    LessonAssignment,
    TeacherMinimumWorkload,
)

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.teacher import Teacher
from app.services import schedule_version as schedule_version_service

# Sort key for a value that may be None: None sorts before any id, so the
# order is total and stable without inventing a sentinel id.
_NONE_FIRST = (0, 0)


def _optional_id_key(value: int | None) -> tuple[int, int]:
    return _NONE_FIRST if value is None else (1, value)


def _violation_sort_key(
    violation: ConstraintViolation,
) -> tuple[object, ...]:
    """type, lesson_id, time_slot_id first (the Task 61 contract); the
    remaining fields only break ties (e.g. several H7 rows all have
    lesson_id=None) so the order is fully deterministic."""
    return (
        violation.type,
        _optional_id_key(violation.lesson_id),
        _optional_id_key(violation.time_slot_id),
        _optional_id_key(violation.class_subject_requirement_id),
        _optional_id_key(violation.teacher_id),
        _optional_id_key(violation.room_id),
        violation.message,
    )


def _all_hard_constraints(resources: SchedulingResources) -> list[BaseConstraint]:
    """Every Hard Constraint the engine currently implements: H1-H6, H8,
    H9, H11, H12 (build_real_time_constraints with H8 included -- the same
    set Backtracking filters on) plus H7, which the algorithms only ever
    run post-hoc. H10 (room capacity) does not exist in the engine yet.
    Task 88: plus the lesson block rule -- block_constraints(), the very
    list the algorithms search with (empty when no requirement has a
    lesson_pattern). The static feasibility check is deliberately NOT
    included -- it predicts whether a schedule CAN be found, which is
    meaningless for one that already exists."""
    return [
        *build_real_time_constraints(resources, include_teacher_workload=True),
        WeeklyPeriodsConstraint(resources.requirement_periods),
        *block_constraints(resources),
    ]


# Task 62: a Schedule row that exists but is missing its teacher or time
# slot. Every engine constraint that needs those values (H1/H4/H5/...)
# simply skips such a row, so without this check a half-filled timetable
# could come back as valid. Detected here in the service layer, not in
# scheduling_engine/: the engine's own search never produces such a row --
# it only exists in stored data (manual edits, copies).
INCOMPLETE_SCHEDULE_ROW = "INCOMPLETE_SCHEDULE_ROW"


def _incomplete_row_violations(
    assignments: list[LessonAssignment],
) -> list[ConstraintViolation]:
    violations: list[ConstraintViolation] = []
    for assignment in assignments:
        missing = [
            field_name
            for field_name, value in (
                ("teacher", assignment.teacher_id),
                ("time slot", assignment.time_slot_id),
            )
            if value is None
        ]
        if not missing:
            continue
        violations.append(
            ConstraintViolation(
                type=INCOMPLETE_SCHEDULE_ROW,
                severity=Severity.ERROR,
                lesson_id=assignment.lesson_id,
                teacher_id=assignment.teacher_id,
                class_id=assignment.class_id,
                subject_id=assignment.subject_id,
                time_slot_id=assignment.time_slot_id,
                room_id=assignment.room_id,
                class_subject_requirement_id=assignment.class_subject_requirement_id,
                message=(
                    f"Lesson {assignment.lesson_id} is in the schedule but has "
                    f"no {' or '.join(missing)} assigned."
                ),
                suggested_action=(
                    "Assign the missing teacher/time slot to this lesson, or "
                    "remove its schedule row."
                ),
            )
        )
    return violations


# Task 66: a Schedule row whose Lesson is pinned (Lesson.fixed_time_slot_id)
# but which currently sits in a different time slot. The engine only honours
# fixed_time_slot_id during run-scheduler's search (it becomes the
# LessonAssignment's starting time slot), so after a manual move/swap nothing
# in scheduling_engine/ knows the lesson was pinned. Same reasoning as
# INCOMPLETE_SCHEDULE_ROW: detected here in the service layer, engine
# untouched. A row with no time slot at all is left to INCOMPLETE_SCHEDULE_ROW.
FIXED_TIME_SLOT_MISMATCH = "FIXED_TIME_SLOT_MISMATCH"


def _load_fixed_time_slots(db: Session, schedule_version_id: int) -> dict[int, int]:
    """lesson_id -> fixed_time_slot_id, for every pinned Lesson that has a
    Schedule row in this version."""
    rows = db.execute(
        select(Lesson.id, Lesson.fixed_time_slot_id)
        .join(Schedule, Schedule.lesson_id == Lesson.id)
        .where(
            Schedule.schedule_version_id == schedule_version_id,
            Lesson.fixed_time_slot_id.is_not(None),
        )
    ).all()
    return {lesson_id: fixed_time_slot_id for lesson_id, fixed_time_slot_id in rows}


def _fixed_time_slot_violations(
    assignments: list[LessonAssignment], fixed_time_slots: dict[int, int]
) -> list[ConstraintViolation]:
    violations: list[ConstraintViolation] = []
    for assignment in assignments:
        fixed_time_slot_id = fixed_time_slots.get(assignment.lesson_id)
        if (
            fixed_time_slot_id is None
            or assignment.time_slot_id is None
            or assignment.time_slot_id == fixed_time_slot_id
        ):
            continue
        violations.append(
            ConstraintViolation(
                type=FIXED_TIME_SLOT_MISMATCH,
                severity=Severity.ERROR,
                lesson_id=assignment.lesson_id,
                teacher_id=assignment.teacher_id,
                class_id=assignment.class_id,
                subject_id=assignment.subject_id,
                time_slot_id=assignment.time_slot_id,
                room_id=assignment.room_id,
                class_subject_requirement_id=assignment.class_subject_requirement_id,
                message=(
                    f"Lesson {assignment.lesson_id} is fixed to time slot "
                    f"{fixed_time_slot_id} but is scheduled in time slot "
                    f"{assignment.time_slot_id}."
                ),
                suggested_action=(
                    f"Move this lesson back to time slot {fixed_time_slot_id}, "
                    "or change its fixed time slot in the scheduler console."
                ),
            )
        )
    return violations


def load_assignment_rows(
    db: Session, schedule_version_id: int
) -> list[tuple[int, LessonAssignment]]:
    """(Schedule.id, LessonAssignment) per Schedule row of this version,
    ordered by Schedule.id, exactly as stored (teacher/time slot/room may be
    None). class_id/subject_id come from each Lesson's own requirement.
    Task 83: the Schedule id is kept so a caller can say which row it
    changes in memory (services/move_candidates.py)."""
    rows = db.execute(
        select(
            Schedule,
            Lesson.class_subject_requirement_id,
            ClassSubjectRequirement.class_id,
            ClassSubjectRequirement.subject_id,
        )
        .join(Lesson, Schedule.lesson_id == Lesson.id)
        .join(
            ClassSubjectRequirement,
            Lesson.class_subject_requirement_id == ClassSubjectRequirement.id,
        )
        .where(Schedule.schedule_version_id == schedule_version_id)
        .order_by(Schedule.id)
    ).all()

    return [
        (
            schedule.id,
            LessonAssignment(
                lesson_id=schedule.lesson_id,
                class_subject_requirement_id=requirement_id,
                class_id=class_id,
                subject_id=subject_id,
                teacher_id=schedule.teacher_id,
                time_slot_id=schedule.time_slot_id,
                room_id=schedule.room_id,
            ),
        )
        for schedule, requirement_id, class_id, subject_id in rows
    ]


def _load_assignments(
    db: Session, schedule_version_id: int
) -> list[LessonAssignment]:
    """One LessonAssignment per Schedule row of this version, ordered by
    Schedule.id -- see load_assignment_rows()."""
    return [assignment for _, assignment in load_assignment_rows(db, schedule_version_id)]


@dataclass(frozen=True)
class CheckContext:
    """Task 83: everything check_assignments() needs besides the rows
    themselves -- the semester's requirements as engine resources, and the
    fixed time slots of this version's Lessons. Loaded once, so the same
    check can be run in memory on many hypothetical arrangements of the
    version's rows (none of which changes requirements or fixed slots)."""

    resources: SchedulingResources
    fixed_time_slots: dict[int, int]
    # Task 88: lesson_id -> Schedule.id of this version (one row per lesson,
    # uq_schedule_version_lesson). Moves and swaps keep every lesson in its
    # own row, so this holds for every arrangement checked in memory.
    schedule_ids: dict[int, int]
    # Task 88: the minimum weekly periods of every active teacher.
    teacher_minimums: list[TeacherMinimumWorkload]


def _load_schedule_ids(db: Session, schedule_version_id: int) -> dict[int, int]:
    rows = db.execute(
        select(Schedule.lesson_id, Schedule.id).where(
            Schedule.schedule_version_id == schedule_version_id
        )
    ).all()
    return {lesson_id: schedule_id for lesson_id, schedule_id in rows}


def _load_teacher_minimums(db: Session) -> list[TeacherMinimumWorkload]:
    """Active teachers only: an inactive one can't be scheduled at all
    (H12), so "teaching too little" says nothing about them. Ordered by id
    so the warnings come out in a stable order."""
    teachers = db.scalars(
        select(Teacher).where(Teacher.is_active.is_(True)).order_by(Teacher.id)
    ).all()
    return [
        TeacherMinimumWorkload(
            teacher_id=teacher.id, min_weekly_periods=teacher.min_weekly_periods
        )
        for teacher in teachers
    ]


def load_check_context(
    db: Session, semester_id: int, schedule_version_id: int
) -> CheckContext:
    requirements = load_semester_requirements(db, semester_id)
    resources = build_scheduling_resources(db, requirements)
    requirement_ids = [requirement.id for requirement in requirements]
    if requirement_ids:
        # Task 88: the same blocks run-scheduler would search with
        # (build_lesson_blocks), so the check judges exactly its rule.
        lessons = list(
            db.scalars(
                select(Lesson).where(Lesson.class_subject_requirement_id.in_(requirement_ids))
            ).all()
        )
        resources = replace(resources, lesson_blocks=build_lesson_blocks(lessons))
    return CheckContext(
        resources=resources,
        fixed_time_slots=_load_fixed_time_slots(db, schedule_version_id),
        schedule_ids=_load_schedule_ids(db, schedule_version_id),
        teacher_minimums=_load_teacher_minimums(db),
    )


def _with_schedule_id(
    violation: ConstraintViolation, schedule_ids: dict[int, int]
) -> ConstraintViolation:
    if violation.lesson_id is None or violation.lesson_id not in schedule_ids:
        return violation
    return replace(violation, schedule_id=schedule_ids[violation.lesson_id])


def check_assignments(
    context: CheckContext, assignments: list[LessonAssignment]
) -> list[ConstraintViolation]:
    """The check itself, pure and in memory: every violation in
    `assignments` (rows of one version), sorted by type, lesson_id,
    time_slot_id. check_schedule_version() is exactly this over the rows
    as stored."""
    violations: list[ConstraintViolation] = _incomplete_row_violations(assignments)
    violations.extend(_fixed_time_slot_violations(assignments, context.fixed_time_slots))
    for constraint in _all_hard_constraints(context.resources):
        violations.extend(constraint.explain_violations(assignments))
    # Task 88: a WARNING only -- see TeacherMinWorkloadConstraint.
    violations.extend(
        TeacherMinWorkloadConstraint(context.teacher_minimums).explain_violations(assignments)
    )
    return sorted(
        (_with_schedule_id(violation, context.schedule_ids) for violation in violations),
        key=_violation_sort_key,
    )


def has_errors(violations: list[ConstraintViolation]) -> bool:
    """Task 88: whether the timetable is invalid -- any ERROR. A WARNING
    (TEACHER_MIN_WORKLOAD) alone leaves it valid."""
    return any(violation.severity == Severity.ERROR for violation in violations)


def check_schedule_version(
    db: Session, schedule_version_id: int, *, role: str | None = None
) -> list[ConstraintViolation] | None:
    """Returns None if the ScheduleVersion doesn't exist -- or, for a
    TEACHER, isn't PUBLISHED (same visibility rule as
    get_schedule_version(); caller -> 404). Otherwise returns every Hard
    Constraint violation in the version's current Schedule rows, sorted by
    type, lesson_id, time_slot_id. Besides the engine's Hard Constraints,
    a Schedule row missing its teacher or time slot is reported as
    INCOMPLETE_SCHEDULE_ROW (Task 62), and a pinned Lesson sitting outside
    its fixed time slot as FIXED_TIME_SLOT_MISMATCH (Task 66). Task 88: lesson
    block violations (BLOCK_NOT_CONSECUTIVE / BLOCK_SAME_DAY) and the
    TEACHER_MIN_WORKLOAD warning are included too. An empty list -- or one
    with only WARNINGs -- means the timetable is valid. A version with no Schedule rows at all is checked as-is (H7
    then reports every requirement as under-scheduled)."""
    schedule_version = schedule_version_service.get_schedule_version(
        db, schedule_version_id, role=role
    )
    if schedule_version is None:
        return None

    context = load_check_context(db, schedule_version.semester_id, schedule_version_id)
    return check_assignments(context, _load_assignments(db, schedule_version_id))
