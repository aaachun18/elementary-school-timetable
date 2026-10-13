"""Task 63: reassign one course (one ClassSubjectRequirement) to a new
teacher within a DRAFT ScheduleVersion, then report the version's full
schedule check.

This is a manual adjustment, not re-scheduling: only teachers change --
no lesson moves to another time slot or room. Two places hold the teacher
and both are updated:
- ClassSubjectRequirement.required_teacher_id (shared by every version in
  the semester -- a known trade-off, see docs/SYSTEM_DESIGN.md);
- teacher_id on this version's Schedule rows for that requirement's
  Lessons (other versions' rows are never touched).

Only a missing record, a PUBLISHED version, a requirement from another
semester, or an inactive new teacher is refused. Qualification (H5),
availability (H4), workload (H8) and double-booking (H1) do NOT block: the
change is still saved, and the returned check lists them. dry_run performs
exactly the same update and check, then rolls everything back.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.teacher import Teacher
from app.services import schedule_check
from app.services.exceptions import (
    InactiveTeacherAssignmentError,
    PublishedVersionImmutableError,
    ReassignmentTargetNotFoundError,
    RequirementSemesterMismatchError,
)

# schedule_check returns the engine's own ConstraintViolation objects; the
# alias keeps this module from importing scheduling_engine directly (see
# services/scheduler.py's module docstring).
ConstraintViolation = schedule_check.ConstraintViolation


@dataclass
class ReassignmentOutcome:
    previous_teacher_id: int | None
    updated_schedule_row_count: int
    violations: list[ConstraintViolation]


def _validate(
    db: Session, schedule_version: ScheduleVersion, requirement_id: int, new_teacher_id: int
) -> ClassSubjectRequirement:
    """Every refusal happens here, before anything is changed."""
    if schedule_version.status == "PUBLISHED":
        raise PublishedVersionImmutableError(
            f"ScheduleVersion {schedule_version.id} is PUBLISHED and "
            "cannot be modified."
        )

    requirement = db.get(ClassSubjectRequirement, requirement_id)
    if requirement is None:
        raise ReassignmentTargetNotFoundError("ClassSubjectRequirement not found")
    if requirement.semester_id != schedule_version.semester_id:
        raise RequirementSemesterMismatchError(
            f"ClassSubjectRequirement {requirement_id} is in semester "
            f"{requirement.semester_id}, not ScheduleVersion "
            f"{schedule_version.id}'s semester {schedule_version.semester_id}."
        )

    new_teacher = db.get(Teacher, new_teacher_id)
    if new_teacher is None:
        raise ReassignmentTargetNotFoundError("Teacher not found")
    if not new_teacher.is_active:
        raise InactiveTeacherAssignmentError(
            f"Teacher {new_teacher_id} is inactive and cannot be assigned."
        )
    return requirement


def _schedule_rows_of_requirement(
    db: Session, schedule_version_id: int, requirement_id: int
) -> list[Schedule]:
    return list(
        db.scalars(
            select(Schedule)
            .join(Lesson, Schedule.lesson_id == Lesson.id)
            .where(
                Schedule.schedule_version_id == schedule_version_id,
                Lesson.class_subject_requirement_id == requirement_id,
            )
            .order_by(Schedule.id)
        ).all()
    )


def _previous_teacher_id(
    requirement: ClassSubjectRequirement, rows: list[Schedule]
) -> int | None:
    """The teacher this course had in this version before the change: the
    one teacher on all of its Schedule rows when they agree (what the
    timetable actually shows), otherwise the requirement's own
    required_teacher_id (no rows, or rows with mixed/missing teachers)."""
    row_teacher_ids = {row.teacher_id for row in rows}
    if len(row_teacher_ids) == 1:
        (only_teacher_id,) = row_teacher_ids
        if only_teacher_id is not None:
            return only_teacher_id
    return requirement.required_teacher_id


def reassign_teacher(
    db: Session,
    schedule_version_id: int,
    requirement_id: int,
    new_teacher_id: int,
    *,
    dry_run: bool,
) -> ReassignmentOutcome | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).
    Raises PublishedVersionImmutableError / ReassignmentTargetNotFoundError
    / RequirementSemesterMismatchError / InactiveTeacherAssignmentError
    before changing anything. Otherwise updates the requirement and this
    version's matching Schedule rows, runs the schedule check against the
    updated (flushed) state, and commits -- even when the check finds
    violations -- or rolls back when dry_run is True.

    updated_schedule_row_count is the number of this version's Schedule
    rows for the requirement, i.e. every row whose teacher_id is set to the
    new teacher (rows that already had that teacher included).
    """
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None

    requirement = _validate(db, schedule_version, requirement_id, new_teacher_id)

    try:
        rows = _schedule_rows_of_requirement(db, schedule_version_id, requirement_id)
        previous_teacher_id = _previous_teacher_id(requirement, rows)

        requirement.required_teacher_id = new_teacher_id
        for row in rows:
            row.teacher_id = new_teacher_id
        db.flush()

        # role=None: the check runs with full (ADMIN) visibility.
        violations = schedule_check.check_schedule_version(db, schedule_version_id)
        assert violations is not None  # the version was found above

        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        # Not swallowed: re-raised after undoing every staged change, so a
        # failure never leaves a half-updated requirement/timetable.
        db.rollback()
        raise

    return ReassignmentOutcome(
        previous_teacher_id=previous_teacher_id,
        updated_schedule_row_count=len(rows),
        violations=violations,
    )
