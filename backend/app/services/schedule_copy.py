"""Task 62: copy a ScheduleVersion into a new DRAFT version.

Two modes, decided by target_semester_id:
- Same semester (omitted, or equal to the source's semester): requirements
  and Lessons are shared by every version in a semester, so only a new
  ScheduleVersion and copies of the source's Schedule rows are created --
  each copied row keeps the same lesson_id.
- Cross semester (a different semester in the same academic year): the
  source semester's requirements and ALL their Lessons are copied into the
  target semester too, and each copied Schedule row is remapped onto the
  matching new Lesson.

The copy is verbatim: no conflict check, no re-scheduling, nulls kept as
null, a conflicting source copied as-is (GET .../check is how the caller
finds out). The source is only ever read. Everything happens in one
transaction: any failure rolls back the whole copy, leaving nothing behind.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import DRAFT, ScheduleVersion
from app.services.exceptions import (
    CopyAcrossAcademicYearsError,
    CopySourceInconsistentError,
    TargetSemesterHasRequirementsError,
    TargetSemesterNotFoundError,
    raise_for_integrity_error,
)

# Every business column of ClassSubjectRequirement, copied verbatim
# (required_teacher_id included even if that teacher is now inactive -- the
# check reports H12 for it). Not copied: id (new row), semester_id (set to
# the target), created_at/updated_at (TimestampMixin, new row's own).
# tests/test_schedule_copy.py checks that these two lists together cover
# every column, so a column added to the model later can't be silently
# left out of the copy.
COPIED_REQUIREMENT_FIELDS = (
    "class_id",
    "subject_id",
    "weekly_periods",
    "required_teacher_id",
    "required_room_type",
    "consecutive_limit",
)
NOT_COPIED_REQUIREMENT_FIELDS = ("id", "semester_id", "created_at", "updated_at")

NEW_VERSION_STATUS = DRAFT


def _next_version_number(db: Session, semester_id: int) -> int:
    current_max = db.scalar(
        select(func.max(ScheduleVersion.version_number)).where(
            ScheduleVersion.semester_id == semester_id
        )
    )
    return 1 if current_max is None else current_max + 1


def _resolve_target_semester_id(
    db: Session, source_semester_id: int, target_semester_id: int | None
) -> int:
    """Validates a cross-semester target (exists, same academic year) and
    returns the semester the new version belongs to. Only reads."""
    if target_semester_id is None or target_semester_id == source_semester_id:
        return source_semester_id

    target_semester = db.get(Semester, target_semester_id)
    if target_semester is None:
        raise TargetSemesterNotFoundError(
            f"Semester {target_semester_id} does not exist."
        )
    source_semester = db.get(Semester, source_semester_id)
    assert source_semester is not None  # FK on schedule_versions.semester_id
    if target_semester.academic_year_id != source_semester.academic_year_id:
        raise CopyAcrossAcademicYearsError(
            f"Semester {target_semester_id} is not in the same academic year "
            f"as semester {source_semester_id}."
        )
    target_has_requirements = db.scalar(
        select(ClassSubjectRequirement.id)
        .where(ClassSubjectRequirement.semester_id == target_semester_id)
        .limit(1)
    )
    if target_has_requirements is not None:
        raise TargetSemesterHasRequirementsError(
            f"Semester {target_semester_id} already has requirements."
        )
    return target_semester_id


def _stage_requirement_and_lesson_copies(
    db: Session, source_semester_id: int, target_semester_id: int
) -> dict[int, int]:
    """Stages copies of every requirement in the source semester and every
    Lesson under them (scheduled or not). Returns {old lesson id: new
    lesson id}, matched by (old requirement, sequence_number)."""
    source_requirements = db.scalars(
        select(ClassSubjectRequirement)
        .where(ClassSubjectRequirement.semester_id == source_semester_id)
        .order_by(ClassSubjectRequirement.id)
    ).all()
    new_requirement_by_old_id = {
        requirement.id: ClassSubjectRequirement(
            semester_id=target_semester_id,
            **{field: getattr(requirement, field) for field in COPIED_REQUIREMENT_FIELDS},
        )
        for requirement in source_requirements
    }
    db.add_all(new_requirement_by_old_id.values())
    db.flush()  # assigns the new requirement ids the Lessons need

    source_lessons = (
        db.scalars(
            select(Lesson)
            .where(
                Lesson.class_subject_requirement_id.in_(list(new_requirement_by_old_id))
            )
            .order_by(Lesson.id)
        ).all()
        if new_requirement_by_old_id
        else []
    )
    new_lesson_by_old_id = {
        lesson.id: Lesson(
            class_subject_requirement_id=new_requirement_by_old_id[
                lesson.class_subject_requirement_id
            ].id,
            sequence_number=lesson.sequence_number,
            fixed_time_slot_id=lesson.fixed_time_slot_id,
        )
        for lesson in source_lessons
    }
    db.add_all(new_lesson_by_old_id.values())
    db.flush()  # assigns the new lesson ids the Schedule rows need

    return {old_id: new_lesson.id for old_id, new_lesson in new_lesson_by_old_id.items()}


def _stage_schedule_copies(
    db: Session,
    source_version_id: int,
    new_version_id: int,
    lesson_id_map: dict[int, int] | None,
) -> None:
    """Stages a copy of every Schedule row of the source version.
    lesson_id_map is None for a same-semester copy (lesson_id kept as-is)."""
    source_schedules = db.scalars(
        select(Schedule)
        .where(Schedule.schedule_version_id == source_version_id)
        .order_by(Schedule.id)
    ).all()

    new_schedules: list[Schedule] = []
    for schedule in source_schedules:
        lesson_id = schedule.lesson_id
        if lesson_id_map is not None:
            if lesson_id not in lesson_id_map:
                raise CopySourceInconsistentError(
                    f"Schedule {schedule.id} points at Lesson {lesson_id}, "
                    "which is not under the source semester's requirements."
                )
            lesson_id = lesson_id_map[lesson_id]
        new_schedules.append(
            Schedule(
                schedule_version_id=new_version_id,
                lesson_id=lesson_id,
                teacher_id=schedule.teacher_id,
                time_slot_id=schedule.time_slot_id,
                room_id=schedule.room_id,
            )
        )
    db.add_all(new_schedules)
    db.flush()


def _stage_copy(
    db: Session, source: ScheduleVersion, target_semester_id: int
) -> ScheduleVersion:
    new_version = ScheduleVersion(
        semester_id=target_semester_id,
        version_number=_next_version_number(db, target_semester_id),
        status=NEW_VERSION_STATUS,
    )
    db.add(new_version)
    db.flush()

    lesson_id_map = (
        None
        if target_semester_id == source.semester_id
        else _stage_requirement_and_lesson_copies(
            db, source.semester_id, target_semester_id
        )
    )
    _stage_schedule_copies(db, source.id, new_version.id, lesson_id_map)
    return new_version


def copy_schedule_version(
    db: Session, source_version_id: int, target_semester_id: int | None
) -> ScheduleVersion | None:
    """Returns None if the source ScheduleVersion doesn't exist (caller ->
    404). Raises TargetSemesterNotFoundError / CopyAcrossAcademicYearsError /
    TargetSemesterHasRequirementsError before writing anything, and
    CopySourceInconsistentError (rolled back) if the source has a Schedule
    row outside its own semester. A version_number race with another
    writer surfaces as DuplicateValueError (409), also rolled back.
    Otherwise returns the new DRAFT version, committed in one transaction.
    """
    source = db.get(ScheduleVersion, source_version_id)
    if source is None:
        return None

    resolved_target_id = _resolve_target_semester_id(
        db, source.semester_id, target_semester_id
    )

    try:
        new_version = _stage_copy(db, source, resolved_target_id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    except Exception:
        # Not swallowed: any other failure part-way through is re-raised
        # after undoing everything staged so far, so no half-copy remains.
        db.rollback()
        raise
    db.refresh(new_version)
    return new_version
