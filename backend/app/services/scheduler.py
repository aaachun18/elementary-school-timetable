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
    ClassAllowedTimeSlots,
    DefaultRoom,
    LessonAssignment,
    LessonBlock,
    RequiredRoomRule,
    RequiredTeacherRule,
    RequirementPeriods,
    TeacherUnavailability,
    TeacherWorkloadLimit,
    TimeSlotInfo,
    TimeSlotPosition,
)
from scheduling_engine.static_feasibility import (  # noqa: E402
    CLASS_SLOTS_INSUFFICIENT,
    FIXED_SLOT_ROOM_CLASH,
    ROOM_OVERBOOKED,
    check_static_feasibility,
)

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.semester_grade_time_slot import SemesterGradeTimeSlot
from app.models.semester_teacher import SemesterTeacher, SemesterTeacherUnavailability
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.time_slot import TimeSlot
from app.services.school_scope import in_school, school_id_of_version
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


def build_lesson_blocks(lessons: list[Lesson]) -> list[LessonBlock]:
    """Task 87: the engine's LessonBlocks from the Lessons' block_no /
    block_seq, members in block_seq order. Lessons without block fields
    belong to no block. Task 88: shared with the schedule check
    (services/schedule_check.py), so both see the same blocks."""
    members: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for lesson in lessons:
        if lesson.block_no is not None and lesson.block_seq is not None:
            members.setdefault((lesson.class_subject_requirement_id, lesson.block_no), []).append(
                (lesson.block_seq, lesson.id)
            )
    return [
        LessonBlock(
            class_subject_requirement_id=requirement_id,
            block_no=block_no,
            lesson_ids=tuple(lesson_id for _, lesson_id in sorted(seq_and_ids)),
        )
        for (requirement_id, block_no), seq_and_ids in sorted(members.items())
    ]


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
    lesson_blocks = build_lesson_blocks(lessons_orm)

    resources = build_scheduling_resources(
        db,
        requirements,
        semester_id=schedule_version.semester_id,
        school_id=school_id_of_version(db, schedule_version),
    )
    if lesson_blocks:
        resources = replace(resources, lesson_blocks=lesson_blocks)
    return lessons, resources


def load_semester_teachers(
    db: Session, semester_id: int, school_id: int
) -> list[SemesterTeacher]:
    """Task 98: the teachers taking part in the semester's scheduling, in
    teacher id order (the order the search tries them in). Only the
    school's own teachers, even if a row ever named another school's."""
    return list(
        db.scalars(
            select(SemesterTeacher)
            .join(Teacher, SemesterTeacher.teacher_id == Teacher.id)
            .where(
                SemesterTeacher.semester_id == semester_id,
                in_school(Teacher, school_id),
            )
            .order_by(SemesterTeacher.teacher_id)
        ).all()
    )


def _class_allowed_time_slots(
    db: Session, semester_id: int, classes: list[Class]
) -> list[ClassAllowedTimeSlots]:
    """H13: each class gets its grade's open slots for the semester. A
    grade with no SemesterGradeTimeSlot row at all for the semester has no
    restriction (no entry) -- the wizard always saves at least one slot."""
    slots_by_grade: dict[int, set[int]] = {}
    for grade_id, time_slot_id in db.execute(
        select(SemesterGradeTimeSlot.grade_id, SemesterGradeTimeSlot.time_slot_id).where(
            SemesterGradeTimeSlot.semester_id == semester_id
        )
    ).all():
        slots_by_grade.setdefault(grade_id, set()).add(time_slot_id)
    return [
        ClassAllowedTimeSlots(
            class_id=class_.id, time_slot_ids=frozenset(slots_by_grade[class_.grade_id])
        )
        for class_ in classes
        if class_.grade_id in slots_by_grade
    ]


def build_scheduling_resources(
    db: Session,
    requirements: list[ClassSubjectRequirement],
    *,
    semester_id: int,
    school_id: int,
) -> SchedulingResources:
    """Converts the DB's reference data into the engine's
    SchedulingResources. Task 61: pulled out of
    _build_lessons_and_resources() so the read-only schedule check
    (services/schedule_check.py) validates against exactly the same
    resources the scheduler searches with.

    Per-requirement rules (required teacher, required room, weekly periods)
    come from `requirements` -- one semester's ClassSubjectRequirements.
    Task 98: the teachers, their weekly maximum and unavailable slots, and
    the slots each grade is open for are the semester's own settings
    (SemesterTeacher / SemesterTeacherUnavailability /
    SemesterGradeTimeSlot); rooms, time slots and active statuses are the
    school's. Never another school's teachers, rooms or time slots.
    """
    semester_teachers = load_semester_teachers(db, semester_id, school_id)
    teacher_unavailability = [
        TeacherUnavailability(
            teacher_id=semester_teacher.teacher_id, time_slot_id=row.time_slot_id
        )
        for semester_teacher in semester_teachers
        for row in db.scalars(
            select(SemesterTeacherUnavailability)
            .where(SemesterTeacherUnavailability.semester_teacher_id == semester_teacher.id)
            .order_by(SemesterTeacherUnavailability.time_slot_id)
        ).all()
    ]
    required_teacher_rules = [
        RequiredTeacherRule(
            class_subject_requirement_id=requirement.id,
            required_teacher_id=requirement.required_teacher_id,
        )
        for requirement in requirements
        if requirement.required_teacher_id is not None
    ]
    required_room_rules = [
        RequiredRoomRule(
            class_subject_requirement_id=requirement.id,
            room_id=requirement.required_room_id,
        )
        for requirement in requirements
        if requirement.required_room_id is not None
    ]

    all_rooms = list(db.scalars(select(Room).where(in_school(Room, school_id))).all())
    all_time_slots = list(
        db.scalars(select(TimeSlot).where(in_school(TimeSlot, school_id))).all()
    )
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

    all_teachers = list(
        db.scalars(select(Teacher).where(in_school(Teacher, school_id))).all()
    )
    all_classes = list(db.scalars(select(Class).where(in_school(Class, school_id))).all())
    all_subjects = list(
        db.scalars(select(Subject).where(in_school(Subject, school_id))).all()
    )

    # Task 92B: a requirement with no special room (原班上課) is held in its
    # class's homeroom, when the class has one (decision 29). A required
    # room wins over it inside the engine (room_by_requirement()).
    homeroom_by_class = {class_.id: class_.homeroom_room_id for class_ in all_classes}
    default_rooms = [
        DefaultRoom(
            class_subject_requirement_id=requirement.id,
            room_id=homeroom_by_class[requirement.class_id],  # type: ignore[arg-type]
        )
        for requirement in requirements
        if requirement.required_room_id is None
        and homeroom_by_class.get(requirement.class_id) is not None
    ]

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
            teacher_id=semester_teacher.teacher_id,
            max_weekly_periods=semester_teacher.max_weekly_periods,
        )
        for semester_teacher in semester_teachers
    ]

    return SchedulingResources(
        time_slot_ids=time_slot_ids,
        teacher_ids=[semester_teacher.teacher_id for semester_teacher in semester_teachers],
        teacher_unavailability=teacher_unavailability,
        required_teacher_rules=required_teacher_rules,
        required_room_rules=required_room_rules,
        time_slots=time_slots,
        time_slot_positions=time_slot_positions,
        active_statuses=active_statuses,
        requirement_periods=requirement_periods,
        teacher_workload_limits=teacher_workload_limits,
        default_rooms=default_rooms,
        class_allowed_time_slots=_class_allowed_time_slots(db, semester_id, all_classes),
    )


def _name_room_violations(
    db: Session, violations: list[ConstraintViolation]
) -> list[ConstraintViolation]:
    """Task 92B / 98: the engine's room and grade-slot pre-checks can only
    name ids; the frontend has no sentence of its own for them yet, so
    their message is what the user reads. Rewritten here with the class and
    room names (every other violation is returned as is)."""
    def class_name(class_id: int | None) -> str:
        class_ = db.get(Class, class_id) if class_id is not None else None
        return class_.name if class_ is not None else f"班級 {class_id}"

    def room_name(room_id: int | None) -> str:
        room = db.get(Room, room_id) if room_id is not None else None
        return room.name if room is not None else f"教室 {room_id}"

    named: list[ConstraintViolation] = []
    for violation in violations:
        message = violation.message
        if violation.type == ROOM_OVERBOOKED:
            # The engine's text is "教室 {room_id} 要上…（班級 {ids}）"
            # (static_feasibility._check_rooms()): the room is renamed and
            # the counts in between kept.
            counts = violation.message.removeprefix(f"教室 {violation.room_id}")
            counts = counts.rsplit("（班級 ", 1)[0].strip()
            message = f"教室「{room_name(violation.room_id)}」{counts}"
        elif violation.type == FIXED_SLOT_ROOM_CLASH:
            message = (
                f"多個班級都在「{room_name(violation.room_id)}」上課，"
                "而且都有課固定在同一個時段，這間教室同一時段只能上一堂課"
            )
        elif violation.type == CLASS_SLOTS_INSUFFICIENT:
            # The engine's text starts "班級 {class_id} 每週要上…"
            # (static_feasibility._check_class_time_slots()).
            message = violation.message.replace(
                f"班級 {violation.class_id} ", class_name(violation.class_id), 1
            )
        named.append(replace(violation, message=message))
    return named


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
            static_violations=_name_room_violations(db, static_check.violations),
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
