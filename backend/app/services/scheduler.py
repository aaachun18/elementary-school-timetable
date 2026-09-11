"""Bridges the database to the framework-independent scheduling_engine/
package: reads the DB rows a ScheduleVersion's semester needs scheduled,
converts them into scheduling_engine's plain dataclasses, runs the
Backtracking Scheduler, and (on success) writes the result back as
Schedule rows.

This is the ONLY file in backend/app/ that imports scheduling_engine.
Nothing under scheduling_engine/ imports anything from here, or from
SQLAlchemy/FastAPI at all -- see AGENTS.md section 4.
"""

import sys
from dataclasses import dataclass
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
from scheduling_engine.algorithms.resources import SchedulingResources  # noqa: E402
from scheduling_engine.constraints.base import ConstraintViolation  # noqa: E402
from scheduling_engine.models.domain import (  # noqa: E402
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
    PublishedVersionImmutableError,
    ScheduleVersionAlreadyScheduledError,
    raise_for_integrity_error,
)


def _build_lessons_and_resources(
    db: Session, schedule_version: ScheduleVersion
) -> tuple[list[LessonAssignment], SchedulingResources]:
    """Read + convert step. Lesson is version-independent (see
    app/models/lesson.py), so this actually queries by the ScheduleVersion's
    *semester*, not the version itself -- every requirement in that
    semester, and every Lesson already generated for them (via
    generate-lessons, a separate, earlier Task).

    Reference data (teacher qualifications/availability, room/time-slot
    info, active status, workload limits) is queried globally rather than
    scoped down to "only what's relevant" -- any teacher/room in the
    system could in principle be a candidate, and at this project's scale
    there's no benefit to a narrower query, only more code.
    """
    semester_id = schedule_version.semester_id

    requirements = list(
        db.scalars(
            select(ClassSubjectRequirement).where(
                ClassSubjectRequirement.semester_id == semester_id
            )
        ).all()
    )
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
            time_slot_id=None,
            room_id=None,
        )
        for lesson in lessons_orm
    ]

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

    resources = SchedulingResources(
        time_slot_ids=time_slot_ids,
        teacher_qualifications=teacher_qualifications,
        teacher_unavailability=teacher_unavailability,
        required_teacher_rules=required_teacher_rules,
        room_type_requirements=room_type_requirements,
        rooms=rooms,
        time_slots=time_slots,
        active_statuses=active_statuses,
        requirement_periods=requirement_periods,
        teacher_workload_limits=teacher_workload_limits,
    )

    return lessons, resources


@dataclass
class SchedulerRunOutcome:
    """What run_scheduler() returns once the ScheduleVersion is confirmed to
    exist and not already scheduled (see run_scheduler()'s own docstring
    for the None-return and raised-exception cases, which happen earlier).

    Exactly one of the two fields is populated (same "exactly one of these"
    convention already used by GreedyResult/BacktrackingResult):
    - static_violations: the Task 23 pre-search static feasibility check
      found at least one aggregate, summed-up reason this can never
      succeed. schedule_backtracking() was never even called.
    - search_result: the static checks passed, and Backtracking actually
      ran -- see BacktrackingResult for its own success/failure shape.
    """

    static_violations: list[ConstraintViolation] | None
    search_result: BacktrackingResult | None


def run_scheduler(
    db: Session, schedule_version_id: int
) -> SchedulerRunOutcome | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).

    Raises ScheduleVersionAlreadyScheduledError if this version already has
    Schedule rows (see that exception's docstring for why re-running isn't
    just allowed to silently overwrite them).

    Otherwise runs the Task 23 static feasibility checks first -- three
    aggregate, summed-up facts (teacher workload, teacher availability,
    inactive entities) that settle infeasibility without a single search
    step -- and only calls schedule_backtracking() if all three pass. In
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

    if schedule_version.status == "PUBLISHED":
        # Task 25: a PUBLISHED version is fully locked -- checked before
        # the already-scheduled guard below, since that guard is specific
        # to run-scheduler while this one is the more fundamental gate
        # shared by every mutating operation on a ScheduleVersion.
        raise PublishedVersionImmutableError(
            f"ScheduleVersion {schedule_version_id} is PUBLISHED and "
            "cannot be modified."
        )

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
            static_violations=static_check.violations, search_result=None
        )

    result = schedule_backtracking(lessons, resources)

    if result.success and result.state is not None:
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

    return SchedulerRunOutcome(static_violations=None, search_result=result)
