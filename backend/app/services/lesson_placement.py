"""Task 92: lessons of a ScheduleVersion's semester that have no Schedule row
in that version yet ("unscheduled" -- e.g. a requirement added after the
version was scheduled), and placing them into a DRAFT version by hand.

Lessons are shared by every version of a semester (app/models/lesson.py),
so a requirement added after scheduling gets lessons no existing version
has a row for, and the check reports the weekly periods as short. Three
operations, all ADMIN-only (decision 28):

- list_unscheduled_lessons(): read-only, any version status.
- list_place_candidates(): read-only "what if" for every time slot, DRAFT
  only, in memory like move-candidates (services/move_candidates.py).
- place_lesson(): creates the rows -- insert -> flush -> the version's full
  schedule check -> commit, or roll back for dry_run (the same flow as
  move-lesson). All or nothing.

Where the lessons go is planned by Layout.plan_place() in
services/block_adjustment.py (a lesson of a block is placed with the
unplaced rest of its block), and every check is check_assignments() --
the same pure function GET /check runs -- so the candidates, the preview
and the check after placing can't disagree.

Teacher: the request's teacher_id, else the requirement's required teacher,
else refused (TEACHER_REQUIRED). Room (Task 92B, decision 29 -- the same
rule as run-scheduler): the request's room_id; else, for a requirement
with no room type (原班上課), the class's homeroom; else none. For a
requirement with a room type nothing is picked: the user names the room
(H9 only compares a room that is there, so an empty one is not reported).
Qualification, availability, workload and double-booking never block a
placement: the check reports them.
"""

from dataclasses import dataclass, replace

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherSubject
from app.models.time_slot import TimeSlot
from app.services import block_adjustment, schedule_check
from app.services.exceptions import (
    AdjustmentTargetNotFoundError,
    InactiveTeacherAssignmentError,
    LessonAlreadyScheduledError,
    LessonNotInSemesterError,
    PlacementRefusedError,
)
from app.services.schedule_version import raise_if_version_locked

ConstraintViolation = schedule_check.ConstraintViolation
LessonAssignment = schedule_check.LessonAssignment

TEACHER_REQUIRED = "TEACHER_REQUIRED"

PLACEMENT_REFUSAL_MESSAGES = {
    TEACHER_REQUIRED: "這堂課的需求沒有指定教師，請先選擇教師",
    block_adjustment.NON_TEACHING_SLOT: "目標時段不是上課時段",
    block_adjustment.BLOCK_OUT_OF_RANGE: (
        "連堂整組放不進這個位置，整組需要同一天相鄰的教學時段"
    ),
    block_adjustment.BLOCK_TARGET_OCCUPIED: "要放入的時段已有本班的其他課",
    block_adjustment.BLOCK_PARTIAL_MISMATCH: (
        "連堂已有部分節次排好，新放入的節必須和已排的節組成同一天相鄰的時段"
    ),
}


# --- The list of unscheduled lessons ---


@dataclass
class EligibleTeacher:
    teacher_id: int
    name: str


@dataclass
class UnscheduledLesson:
    lesson_id: int
    class_subject_requirement_id: int
    class_id: int
    class_name: str
    subject_id: int
    subject_name: str
    sequence_number: int
    required_teacher_id: int | None
    block_no: int | None
    block_seq: int | None
    lesson_pattern: str | None
    fixed_time_slot_id: int | None
    # Task 92B: no room type -> the class's homeroom (what placing uses by
    # default, None when the class has none); a room type -> the first
    # active room of that type (by id), only a hint: placing doesn't pick it.
    suggested_room_id: int | None
    # Active teachers qualified for the subject (TeacherSubject), by name.
    eligible_teachers: list[EligibleTeacher]
    # Task 94: the requirement's room type (None: 原班上課).
    room_type: str | None = None
    # Task 94: the room place-lesson uses when no room_id is sent --
    # default_room_id(), the very function placing calls.
    default_room_id: int | None = None
    # Task 94: with a room type, whether at least one active room has
    # exactly that type; None when the requirement has no room type (there
    # is nothing to match).
    has_matching_room: bool | None = None


def default_room_id(required_room_type: str | None, homeroom_room_id: int | None) -> int | None:
    """Task 92B / 94: the room a placement gets when the request names
    none -- the class's homeroom for a requirement with no room type
    (原班上課, like run-scheduler), else none. Shared by place-lesson /
    place-candidates and the unscheduled list's default_room_id."""
    return homeroom_room_id if required_room_type is None else None


def _eligible_teachers(db: Session, subject_ids: set[int]) -> dict[int, list[EligibleTeacher]]:
    if not subject_ids:
        return {}
    rows = db.execute(
        select(TeacherSubject.subject_id, Teacher.id, Teacher.name)
        .join(Teacher, TeacherSubject.teacher_id == Teacher.id)
        .where(TeacherSubject.subject_id.in_(subject_ids), Teacher.is_active.is_(True))
        .order_by(Teacher.name, Teacher.id)
    ).all()
    by_subject: dict[int, list[EligibleTeacher]] = {subject_id: [] for subject_id in subject_ids}
    for subject_id, teacher_id, name in rows:
        by_subject[subject_id].append(EligibleTeacher(teacher_id, name))
    return by_subject


def _first_room_of_type(db: Session, room_types: set[str]) -> dict[str, int]:
    if not room_types:
        return {}
    rooms = db.execute(
        select(Room.room_type, Room.id)
        .where(Room.room_type.in_(room_types), Room.is_active.is_(True))
        .order_by(Room.id)
    ).all()
    first: dict[str, int] = {}
    for room_type, room_id in rooms:
        first.setdefault(room_type, room_id)
    return first


def list_unscheduled_lessons(
    db: Session, schedule_version_id: int
) -> list[UnscheduledLesson] | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).
    Every Lesson of the version's semester with no Schedule row in this
    version, ordered by class, subject, block, place in the block (lessons
    of no block last), then sequence number. Read-only, any status."""
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None
    rows = db.execute(
        select(Lesson, ClassSubjectRequirement, Class, Subject.name)
        .join(ClassSubjectRequirement, Lesson.class_subject_requirement_id == ClassSubjectRequirement.id)
        .join(Class, ClassSubjectRequirement.class_id == Class.id)
        .join(Subject, ClassSubjectRequirement.subject_id == Subject.id)
        .where(
            ClassSubjectRequirement.semester_id == schedule_version.semester_id,
            ~exists().where(
                Schedule.schedule_version_id == schedule_version_id,
                Schedule.lesson_id == Lesson.id,
            ),
        )
        .order_by(
            Class.id,
            Subject.id,
            ClassSubjectRequirement.id,
            Lesson.block_no.asc().nulls_last(),
            Lesson.block_seq,
            Lesson.sequence_number,
            Lesson.id,
        )
    ).all()
    teachers = _eligible_teachers(db, {requirement.subject_id for _, requirement, _, _ in rows})
    rooms = _first_room_of_type(
        db,
        {
            requirement.required_room_type
            for _, requirement, _, _ in rows
            if requirement.required_room_type is not None
        },
    )
    return [
        UnscheduledLesson(
            lesson_id=lesson.id,
            class_subject_requirement_id=requirement.id,
            class_id=requirement.class_id,
            class_name=class_.name,
            subject_id=requirement.subject_id,
            subject_name=subject_name,
            sequence_number=lesson.sequence_number,
            required_teacher_id=requirement.required_teacher_id,
            block_no=lesson.block_no,
            block_seq=lesson.block_seq,
            lesson_pattern=requirement.lesson_pattern,
            fixed_time_slot_id=lesson.fixed_time_slot_id,
            suggested_room_id=(
                class_.homeroom_room_id
                if requirement.required_room_type is None
                else rooms.get(requirement.required_room_type)
            ),
            eligible_teachers=list(teachers[requirement.subject_id]),
            room_type=requirement.required_room_type,
            default_room_id=default_room_id(requirement.required_room_type, class_.homeroom_room_id),
            has_matching_room=(
                None
                if requirement.required_room_type is None
                else requirement.required_room_type in rooms
            ),
        )
        for lesson, requirement, class_, subject_name in rows
    ]


# --- Placing: shared by place-candidates and place-lesson ---


@dataclass
class _Prepared:
    """Everything a placement of one lesson needs, loaded once."""

    lesson: Lesson
    requirement: ClassSubjectRequirement
    teacher_id: int
    room_id: int | None
    rows: list[tuple[int, LessonAssignment]]
    context: schedule_check.CheckContext
    layout: block_adjustment.Layout
    # lesson_id -> fixed time slot, for the lessons of the requirement.
    fixed_time_slots: dict[int, int]


def _resolve_teacher(
    db: Session, requirement: ClassSubjectRequirement, teacher_id: int | None
) -> int:
    """The request's teacher, else the required one, else TEACHER_REQUIRED.
    A deactivated teacher is refused, as for reassign-teacher."""
    if teacher_id is None:
        teacher_id = requirement.required_teacher_id
        if teacher_id is None:
            raise PlacementRefusedError(TEACHER_REQUIRED)
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        raise AdjustmentTargetNotFoundError("Teacher not found")
    if not teacher.is_active:
        raise InactiveTeacherAssignmentError(f"Teacher {teacher_id} is inactive.")
    return teacher_id


def _prepare(
    db: Session,
    schedule_version_id: int,
    lesson_id: int,
    teacher_id: int | None,
    room_id: int | None,
) -> _Prepared | None:
    """Returns None if the ScheduleVersion doesn't exist. Every refusal
    that doesn't depend on the target slot is raised here, in this order:
    locked version (409), lesson not found (404), lesson of another
    semester (409), lesson already in the version (409), teacher (404 /
    409 TEACHER_REQUIRED / 409 inactive), room not found (404)."""
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None
    raise_if_version_locked(schedule_version)
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise AdjustmentTargetNotFoundError("Lesson not found")
    requirement = db.get(ClassSubjectRequirement, lesson.class_subject_requirement_id)
    assert requirement is not None  # foreign key
    if requirement.semester_id != schedule_version.semester_id:
        raise LessonNotInSemesterError(
            f"Lesson {lesson_id} is not of semester {schedule_version.semester_id}."
        )
    already = db.scalar(
        select(Schedule.id).where(
            Schedule.schedule_version_id == schedule_version_id,
            Schedule.lesson_id == lesson_id,
        )
    )
    if already is not None:
        raise LessonAlreadyScheduledError(
            f"Lesson {lesson_id} already has Schedule {already} in this version."
        )
    resolved_teacher_id = _resolve_teacher(db, requirement, teacher_id)
    if room_id is not None and db.get(Room, room_id) is None:
        raise AdjustmentTargetNotFoundError("Room not found")
    if room_id is None:
        # Task 92B: 原班上課 -> the homeroom, exactly like run-scheduler.
        class_ = db.get(Class, requirement.class_id)
        assert class_ is not None  # foreign key
        room_id = default_room_id(requirement.required_room_type, class_.homeroom_room_id)

    rows = schedule_check.load_assignment_rows(db, schedule_version_id)
    context = schedule_check.load_check_context(db, schedule_version.semester_id, schedule_version_id)
    fixed = db.execute(
        select(Lesson.id, Lesson.fixed_time_slot_id).where(
            Lesson.class_subject_requirement_id == requirement.id,
            Lesson.fixed_time_slot_id.is_not(None),
        )
    ).all()
    return _Prepared(
        lesson=lesson,
        requirement=requirement,
        teacher_id=resolved_teacher_id,
        room_id=room_id,
        rows=rows,
        context=context,
        layout=block_adjustment.Layout(rows, context),
        fixed_time_slots={lesson_id: slot_id for lesson_id, slot_id in fixed},
    )


def _plan(prepared: _Prepared, time_slot_id: int) -> block_adjustment.Placement:
    return prepared.layout.plan_place(
        prepared.lesson.id, prepared.requirement.class_id, time_slot_id
    )


def _check_in_memory(
    prepared: _Prepared, placement: block_adjustment.Placement
) -> list[ConstraintViolation]:
    """The version's check after the placement, without writing anything:
    the stored rows plus one new assignment per placed lesson (after them,
    in block order -- the order place_lesson() inserts them in). The
    placed lessons have no Schedule row, so their violations carry no
    schedule_id."""
    assert placement.lessons is not None
    new = [
        LessonAssignment(
            lesson_id=item.lesson_id,
            class_subject_requirement_id=prepared.requirement.id,
            class_id=prepared.requirement.class_id,
            subject_id=prepared.requirement.subject_id,
            teacher_id=prepared.teacher_id,
            time_slot_id=item.time_slot_id,
            room_id=prepared.room_id,
        )
        for item in placement.lessons
    ]
    fixed = {
        item.lesson_id: prepared.fixed_time_slots[item.lesson_id]
        for item in placement.lessons
        if item.lesson_id in prepared.fixed_time_slots
    }
    context = replace(
        prepared.context,
        fixed_time_slots={**prepared.context.fixed_time_slots, **fixed},
    )
    return schedule_check.check_assignments(context, [a for _, a in prepared.rows] + new)


# --- place-candidates ---


@dataclass
class PlaceCandidate:
    time_slot_id: int
    available: bool
    unavailable_reason: str | None
    # None when the slot is not a target (see unavailable_reason).
    violations: list[ConstraintViolation] | None
    # Every lesson placed with this one (the whole unplaced block); None
    # for a lesson of no block or a slot that is no target.
    block_members: list[block_adjustment.PlacedLesson] | None


@dataclass
class PlaceCandidatesOutcome:
    lesson_id: int
    teacher_id: int
    room_id: int | None
    baseline: list[ConstraintViolation]
    candidates: list[PlaceCandidate]


def list_place_candidates(
    db: Session,
    schedule_version_id: int,
    lesson_id: int,
    teacher_id: int | None,
    room_id: int | None,
) -> PlaceCandidatesOutcome | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404);
    otherwise the same refusals as place_lesson() for everything that
    isn't about the slot (see _prepare()). One candidate per time slot, in
    weekday/period order: each `violations` equals what place-lesson with
    dry_run would report for that slot (same teacher and room)."""
    prepared = _prepare(db, schedule_version_id, lesson_id, teacher_id, room_id)
    if prepared is None:
        return None
    in_block = prepared.layout.is_lesson_in_block(lesson_id)
    time_slots = db.scalars(
        select(TimeSlot).order_by(TimeSlot.weekday, TimeSlot.period, TimeSlot.id)
    ).all()

    candidates: list[PlaceCandidate] = []
    for time_slot in time_slots:
        placement = _plan(prepared, time_slot.id)
        if placement.refusal is not None:
            candidates.append(
                PlaceCandidate(time_slot.id, False, placement.refusal, None, None)
            )
            continue
        assert placement.lessons is not None
        candidates.append(
            PlaceCandidate(
                time_slot.id,
                True,
                None,
                _check_in_memory(prepared, placement),
                list(placement.lessons) if in_block else None,
            )
        )
    return PlaceCandidatesOutcome(
        lesson_id=lesson_id,
        teacher_id=prepared.teacher_id,
        room_id=prepared.room_id,
        baseline=schedule_check.check_assignments(
            prepared.context, [a for _, a in prepared.rows]
        ),
        candidates=candidates,
    )


# --- place-lesson ---


@dataclass
class PlacementChange:
    """One new Schedule row. schedule_id is None for dry_run (the row is
    rolled back, so it has no id worth reporting); the previous_* fields
    are always None -- the lesson had no row -- and are there so a change
    reads like move-lesson's."""

    schedule_id: int | None
    lesson_id: int
    teacher_id: int
    previous_time_slot_id: int | None
    new_time_slot_id: int
    previous_room_id: int | None
    new_room_id: int | None


@dataclass
class PlacementOutcome:
    changes: list[PlacementChange]
    violations: list[ConstraintViolation]


def _new_row(
    db: Session,
    schedule_version_id: int,
    prepared: _Prepared,
    item: block_adjustment.PlacedLesson,
) -> Schedule:
    row = Schedule(
        schedule_version_id=schedule_version_id,
        lesson_id=item.lesson_id,
        teacher_id=prepared.teacher_id,
        time_slot_id=item.time_slot_id,
        room_id=prepared.room_id,
    )
    db.add(row)
    return row


def place_lesson(
    db: Session,
    schedule_version_id: int,
    lesson_id: int,
    time_slot_id: int,
    teacher_id: int | None,
    room_id: int | None,
    *,
    dry_run: bool,
) -> PlacementOutcome | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).
    Refusals (nothing written): see _prepare(), then TimeSlot not found
    (404), then plan_place()'s reason (409 PlacementRefusedError). One row
    per placed lesson (the lesson and the unplaced rest of its block), all
    with the same teacher and room, in one transaction."""
    prepared = _prepare(db, schedule_version_id, lesson_id, teacher_id, room_id)
    if prepared is None:
        return None
    if db.get(TimeSlot, time_slot_id) is None:
        raise AdjustmentTargetNotFoundError("TimeSlot not found")
    placement = _plan(prepared, time_slot_id)
    if placement.refusal is not None:
        raise PlacementRefusedError(placement.refusal)
    assert placement.lessons is not None

    try:
        new_rows = [
            _new_row(db, schedule_version_id, prepared, item) for item in placement.lessons
        ]
        db.flush()
        # role=None: the check runs with full (ADMIN) visibility.
        violations = schedule_check.check_schedule_version(db, schedule_version_id)
        assert violations is not None  # the version was found above
        changes = [
            PlacementChange(
                schedule_id=None if dry_run else row.id,
                lesson_id=row.lesson_id,
                teacher_id=prepared.teacher_id,
                previous_time_slot_id=None,
                new_time_slot_id=row.time_slot_id,  # type: ignore[arg-type]
                previous_room_id=None,
                new_room_id=row.room_id,
            )
            for row in new_rows
        ]
        if dry_run:
            # The rolled-back rows' ids mean nothing: violations about the
            # placed lessons are reported by lesson_id only, exactly as
            # place-candidates reports them.
            placed = {item.lesson_id for item in placement.lessons}
            violations = [
                replace(violation, schedule_id=None) if violation.lesson_id in placed else violation
                for violation in violations
            ]
            db.rollback()
        else:
            db.commit()
    except Exception:
        # Not swallowed: re-raised after undoing every staged row.
        db.rollback()
        raise
    return PlacementOutcome(changes=changes, violations=violations)
