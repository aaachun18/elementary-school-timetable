"""Task 61: read-only "check an existing timetable". Converts a saved
ScheduleVersion's Schedule rows into scheduling_engine LessonAssignments and
runs every existing Hard Constraint's explain_violations() over them.

Unlike run_scheduler(), this never searches and never writes: it only
reports what is wrong with the timetable as it currently stands (DRAFT or
PUBLISHED). Nothing here commits, adds, or modifies any row -- it is the
validation step later features (copy to next semester, reassigning a
teacher, manual edits) can call after the fact.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

# Must be imported before anything from scheduling_engine: importing
# app.services.scheduler runs its sys.path bootstrap, which is what makes
# the repo-root scheduling_engine package importable when the app runs
# with backend/ as the working directory (see that module's comment).
from app.services.scheduler import (
    build_scheduling_resources,
    load_semester_requirements,
)

from scheduling_engine.algorithms.resources import (  # noqa: E402
    SchedulingResources,
    build_real_time_constraints,
)
from scheduling_engine.constraints.base import (  # noqa: E402
    BaseConstraint,
    ConstraintViolation,
)
from scheduling_engine.constraints.weekly_periods import (  # noqa: E402
    WeeklyPeriodsConstraint,
)
from scheduling_engine.models.domain import LessonAssignment  # noqa: E402

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
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
    The static feasibility check is deliberately NOT included -- it
    predicts whether a schedule CAN be found, which is meaningless for one
    that already exists."""
    return [
        *build_real_time_constraints(resources, include_teacher_workload=True),
        WeeklyPeriodsConstraint(resources.requirement_periods),
    ]


def _load_assignments(
    db: Session, schedule_version_id: int
) -> list[LessonAssignment]:
    """One LessonAssignment per Schedule row of this version, exactly as
    stored (teacher/time slot/room may be None). class_id/subject_id come
    from each Lesson's own requirement."""
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
        LessonAssignment(
            lesson_id=schedule.lesson_id,
            class_subject_requirement_id=requirement_id,
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=schedule.teacher_id,
            time_slot_id=schedule.time_slot_id,
            room_id=schedule.room_id,
        )
        for schedule, requirement_id, class_id, subject_id in rows
    ]


def check_schedule_version(
    db: Session, schedule_version_id: int, *, role: str | None = None
) -> list[ConstraintViolation] | None:
    """Returns None if the ScheduleVersion doesn't exist -- or, for a
    TEACHER, isn't PUBLISHED (same visibility rule as
    get_schedule_version(); caller -> 404). Otherwise returns every Hard
    Constraint violation in the version's current Schedule rows, sorted by
    type, lesson_id, time_slot_id. An empty list means the timetable is
    valid. A version with no Schedule rows at all is checked as-is (H7
    then reports every requirement as under-scheduled)."""
    schedule_version = schedule_version_service.get_schedule_version(
        db, schedule_version_id, role=role
    )
    if schedule_version is None:
        return None

    requirements = load_semester_requirements(db, schedule_version.semester_id)
    resources = build_scheduling_resources(db, requirements)
    assignments = _load_assignments(db, schedule_version_id)

    violations: list[ConstraintViolation] = []
    for constraint in _all_hard_constraints(resources):
        violations.extend(constraint.explain_violations(assignments))
    return sorted(violations, key=_violation_sort_key)
