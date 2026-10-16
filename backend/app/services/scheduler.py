"""Bridges the database to the framework-independent scheduling_engine/
package: reads the DB rows a ScheduleVersion's semester needs scheduled,
converts them into scheduling_engine's plain dataclasses, runs the
Backtracking Scheduler, and (on success) writes the result back as
Schedule rows.

This file and services/schedule_check.py (Task 61, which reuses this
file's load_semester_requirements()/build_scheduling_resources() and its
sys.path bootstrap below) are the only files in backend/app/ that import
scheduling_engine. Nothing under scheduling_engine/ imports anything from
here, or from SQLAlchemy/FastAPI at all -- see AGENTS.md section 4.
"""

import sys
from dataclasses import dataclass, replace
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# backend/app/services/scheduler.py -> parents[3] is the repo root, which
# holds scheduling_engine/ as a sibling of backend/ (not a subpackage of
# app/). Mirrors the same sys.path bootstrap already used in
# backend/alembic/env.py and tests/conftest.py for the same
# cross-directory import problem, just in the opposite direction: without
# this, `import scheduling_engine` fails whenever the app is actually run
# with backend/ as the working directory (confirmed while building this
# Task) -- it only happened to work under pytest because tests/conftest.py
# already puts the repo root on sys.path for its own tests.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scheduling_engine.algorithms.backtracking import (  # noqa: E402
    BacktrackingResult,
    schedule_backtracking,
)
from scheduling_engine.algorithms.resources import (  # noqa: E402
    LessonFailure,
    SchedulingResources,
    lessons_moved_off_fixed_slot,
)
from scheduling_engine.constraints.base import ConstraintViolation  # noqa: E402
from scheduling_engine.models.domain import (  # noqa: E402
    ActiveStatusInfo,
    LessonAssignment,
    LessonBlock,
    RequiredTeacherRule,
    RequirementPeriods,
    RoomInfo,
    RoomTypeRequirement,
    TeacherQualification,
    TeacherUnavailability,
    TeacherWorkloadLimit,
    TimeSlotInfo,
    TimeSlotPosition,
)
from scheduling_engine.static_feasibility import check_static_feasibility  # noqa: E402

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherAvailability, TeacherSubject
from app.models.time_slot import TimeSlot
from app.services.exceptions import (
    ScheduleVersionAlreadyScheduledError,
    raise_for_integrity_error,
)
from app.services.schedule_version import raise_if_version_locked


def load_semester_requirements(
    db: Session, semester_id: int
) -> list[ClassSubjectRequirement]:
    """Every ClassSubjectRequirement in one semester. Task 61: pulled out of
    _build_lessons_and_resources() (unchanged query) so the read-only
    schedule check (services/schedule_check.py) loads exactly the same
    requirement set the scheduler does."""
    return list(
        db.scalars(
            select(ClassSubjectRequirement).where(
                ClassSubjectRequirement.semester_id == semester_id
            )
        ).all()
    )


def _build_lessons_and_resources(
    db: Session, schedule_version: ScheduleVersion
) -> tuple[list[LessonAssignment], SchedulingResources]:
    """Read + convert step. Lesson is version-independent (see
    app/models/lesson.py), so this actually queries by the ScheduleVersion's
    *semester*, not the version itself -- every requirement in that
    semester, and every Lesson already generated for them (via
    generate-lessons, a separate, earlier Task).

    Reference data is built by build_scheduling_resources() -- see its
    docstring.
    """
    requirements = load_semester_requirements(db, schedule_version.semester_id)
    requirement_by_id = {requirement.id: requirement for requirement in requirements}

    lessons_orm = (
        list(
            db.scalars(
                select(Lesson).where(
                    Lesson.class_subject_requirement_id.in_(requirement_by_id.keys())
                )
            ).all()
        )
        if requirement_by_id
        else []
    )

    lessons = [
        LessonAssignment(
            lesson_id=lesson.id,
            class_subject_requirement_id=lesson.class_subject_requirement_id,
            class_id=requirement_by_id[lesson.class_subject_requirement_id].class_id,
            subject_id=requirement_by_id[
                lesson.class_subject_requirement_id
            ].subject_id,
            teacher_id=None,
            # Task 28: a Lesson manually fixed to a time slot starts the
            # search with that value already filled in, instead of None --
            # scheduling_engine's candidate_time_slot_ids() treats an
            # already-set time_slot_id as "only candidate", never
            # re-searching it.
            time_slot_id=lesson.fixed_time_slot_id,
            room_id=None,
        )
        for lesson in lessons_orm
    ]

    # Task 87: lessons of one lesson_pattern block are placed as one unit
    # (scheduling_engine/algorithms/blocks.py). Lessons without block
    # fields -- every lesson of a requirement with no pattern -- stay
    # independent, and with no blocks at all the engine runs exactly as
    # before.
    members: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for lesson in lessons_orm:
        if lesson.block_no is not None and lesson.block_seq is not None:
            members.setdefault((lesson.class_subject_requirement_id, lesson.block_no), []).append(
                (lesson.block_seq, lesson.id)
            )
    lesson_blocks = [
        LessonBlock(
            class_subject_requirement_id=requirement_id,
            block_no=block_no,
            lesson_ids=tuple(lesson_id for _, lesson_id in sorted(seq_and_ids)),
        )
        for (requirement_id, block_no), seq_and_ids in sorted(members.items())
    ]

    resources = build_scheduling_resources(db, requirements)
    if lesson_blocks:
        resources = replace(resources, lesson_blocks=lesson_blocks)
    return lessons, resources


def build_scheduling_resources(
    db: Session, requirements: list[ClassSubjectRequirement]
) -> SchedulingResources:
    """Converts the DB's reference data into the engine's
    SchedulingResources. Task 61: pulled out of
    _build_lessons_and_resources() (logic unchanged) so the read-only
    schedule check (services/schedule_check.py) validates against exactly
    the same resources the scheduler searches with.

    Per-requirement rules (required teacher, room type, weekly periods)
    come from `requirements` -- one semester's ClassSubjectRequirements.
    Reference data (teacher qualifications/availability, room/time-slot
    info, active status, workload limits) is queried globally rather than
    scoped down to "only what's relevant" -- any teacher/room in the
    system could in principle be a candidate, and at this project's scale
    there's no benefit to a narrower query, only more code.
    """
    teacher_qualifications = [
        TeacherQualification(teacher_id=row.teacher_id, subject_id=row.subject_id)
        for row in db.scalars(select(TeacherSubject)).all()
    ]
    teacher_unavailability = [
        TeacherUnavailability(teacher_id=row.teacher_id, time_slot_id=row.time_slot_id)
        for row in db.scalars(select(TeacherAvailability)).all()
    ]
    required_teacher_rules = [
        RequiredTeacherRule(
            class_subject_requirement_id=requirement.id,
            required_teacher_id=requirement.required_teacher_id,
        )
        for requirement in requirements
        if requirement.required_teacher_id is not None
    ]
    room_type_requirements = [
        RoomTypeRequirement(
            class_subject_requirement_id=requirement.id,
            required_room_type=requirement.required_room_type,
        )
        for requirement in requirements
        if requirement.required_room_type is not None
    ]

    all_rooms = list(db.scalars(select(Room)).all())
    rooms = [RoomInfo(room_id=room.id, room_type=room.room_type) for room in all_rooms]

    all_time_slots = list(db.scalars(select(TimeSlot)).all())
    time_slots = [
        TimeSlotInfo(
            time_slot_id=time_slot.id,
            is_teaching_period=time_slot.is_teaching_period,
        )
        for time_slot in all_time_slots
    ]
    time_slot_ids = [time_slot.id for time_slot in all_time_slots]
    # Task 87: which slots are consecutive periods of one day (only read
    # for lesson blocks).
    time_slot_positions = [
        TimeSlotPosition(
            time_slot_id=time_slot.id,
            weekday=time_slot.weekday,
            period=time_slot.period,
        )
        for time_slot in all_time_slots
    ]

    all_teachers = list(db.scalars(select(Teacher)).all())
    all_classes = list(db.scalars(select(Class)).all())
    all_subjects = list(db.scalars(select(Subject)).all())

    # H12 needs the REAL is_active value for every entity, active or not --
    # nothing is pre-filtered out here; ActiveStatusConstraint is what
    # decides what to do with an inactive one.
    active_statuses = (
        [
            ActiveStatusInfo(
                entity_type="teacher", entity_id=teacher.id, is_active=teacher.is_active
            )
            for teacher in all_teachers
        ]
        + [
            ActiveStatusInfo(
                entity_type="class", entity_id=class_.id, is_active=class_.is_active
            )
            for class_ in all_classes
        ]
        + [
            ActiveStatusInfo(
                entity_type="subject", entity_id=subject.id, is_active=subject.is_active
            )
            for subject in all_subjects
        ]
        + [
            ActiveStatusInfo(
                entity_type="room", entity_id=room.id, is_active=room.is_active
            )
            for room in all_rooms
        ]
    )

    requirement_periods = [
        RequirementPeriods(
            class_subject_requirement_id=requirement.id,
            weekly_periods=requirement.weekly_periods,
        )
        for requirement in requirements
    ]

    teacher_workload_limits = [
        TeacherWorkloadLimit(
            teacher_id=teacher.id, max_weekly_periods=teacher.max_weekly_periods
        )
        for teacher in all_teachers
    ]

    return SchedulingResources(
        time_slot_ids=time_slot_ids,
        teacher_qualifications=teacher_qualifications,
        teacher_unavailability=teacher_unavailability,
        required_teacher_rules=required_teacher_rules,
        room_type_requirements=room_type_requirements,
        rooms=rooms,
        time_slots=time_slots,
        time_slot_positions=time_slot_positions,
        active_statuses=active_statuses,
        requirement_periods=requirement_periods,
        teacher_workload_limits=teacher_workload_limits,
    )


@dataclass
class SchedulerRunOutcome:
    """What run_scheduler() returns once the ScheduleVersion is confirmed to
    exist and not already scheduled (see run_scheduler()'s own docstring
    for the None-return and raised-exception cases, which happen earlier).

    Exactly one of {static_violations/static_lesson_failures, search_result}
    is populated (same "exactly one of these" convention already used by
    GreedyResult/BacktrackingResult):
    - static_violations/static_lesson_failures: the Task 23 pre-search
      static feasibility check found at least one reason this can never
      succeed -- either a whole-batch one (static_violations: teacher
      workload/availability, inactive entities) or a specific Lesson with
      zero candidate teachers at all (static_lesson_failures, Task 38 --
      see static_feasibility.py's module docstring for why this became a
      4th static check instead of only ever being discovered, or missed,
      inside schedule_backtracking()). schedule_backtracking() was never
      even called.
    - search_result: the static checks passed, and Backtracking actually
      ran -- see BacktrackingResult for its own success/failure shape.
    """

    static_violations: list[ConstraintViolation] | None
    static_lesson_failures: list[LessonFailure] | None
    search_result: BacktrackingResult | None


def run_scheduler(
    db: Session, schedule_version_id: int
) -> SchedulerRunOutcome | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).

    Raises ScheduleVersionAlreadyScheduledError if this version already has
    Schedule rows (see that exception's docstring for why re-running isn't
    just allowed to silently overwrite them).

    Otherwise runs the Task 23 static feasibility checks first -- five facts
    (teacher workload, teacher availability, inactive entities, a Lesson
    with zero candidate teachers at all, and -- Task 81 -- fixed time slots
    that can never be honored) that settle infeasibility without a single
    search step -- and only calls schedule_backtracking() if all of them
    pass. A fixed Lesson can only ever be placed in its fixed slot (the
    search never tries another); that is re-checked before writing. In
    both cases:
    - on success, writes state.assignments to the `schedules` table in one
      commit (caller reads result.search_result.state.assignments /
      backtrack_count for the 200 response).
    - on any failure (static or search), writes nothing at all (matching
      the engine's own atomic guarantee) and returns the failure details
      for the caller to turn into a 422 response.
    """
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None

    # Task 25: a PUBLISHED (Task 64: or ARCHIVED) version is fully locked
    # -- checked before the already-scheduled guard below, since that guard
    # is specific to run-scheduler while this one is the more fundamental
    # gate shared by every mutating operation on a ScheduleVersion.
    raise_if_version_locked(schedule_version)

    existing_count = db.scalar(
        select(Schedule)
        .where(Schedule.schedule_version_id == schedule_version_id)
        .limit(1)
    )
    if existing_count is not None:
        raise ScheduleVersionAlreadyScheduledError(
            f"ScheduleVersion {schedule_version_id} already has Schedule "
            "rows. Delete them first (DELETE /api/v1/schedules/{id}) "
            "before running the scheduler again."
        )

    lessons, resources = _build_lessons_and_resources(db, schedule_version)

    static_check = check_static_feasibility(lessons, resources)
    if not static_check.feasible:
        return SchedulerRunOutcome(
            static_violations=static_check.violations,
            static_lesson_failures=static_check.lesson_failures,
            search_result=None,
        )

    result = schedule_backtracking(lessons, resources)

    if result.success and result.state is not None:
        # Task 81: never write a schedule that moved a fixed Lesson. Cannot
        # happen with the current candidate generation; an engine bug, not
        # a user-facing infeasibility, so it is raised (nothing written).
        moved = lessons_moved_off_fixed_slot(lessons, result.state.assignments)
        if moved:
            raise RuntimeError(
                f"Scheduler placed fixed lesson(s) {moved} outside their "
                "fixed time slot; nothing was written."
            )
        schedule_rows = [
            Schedule(
                schedule_version_id=schedule_version_id,
                lesson_id=assignment.lesson_id,
                teacher_id=assignment.teacher_id,
                time_slot_id=assignment.time_slot_id,
                room_id=assignment.room_id,
            )
            for assignment in result.state.assignments
        ]
        db.add_all(schedule_rows)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise_for_integrity_error(exc)

    return SchedulerRunOutcome(
        static_violations=None, static_lesson_failures=None, search_result=result
    )
