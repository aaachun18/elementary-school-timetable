from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import LOCKED_STATUSES, ScheduleVersion
from app.schemas.class_subject_requirement import (
    ClassSubjectRequirementCreate,
    ClassSubjectRequirementUpdate,
)
from app.services.exceptions import (
    DependentRecordsExistError,
    InvalidLessonPatternError,
    RequirementEditBlockedByPublishedScheduleError,
    RequirementUsedByPublishedScheduleError,
    raise_for_integrity_error,
)
from app.services.lesson_pattern import assign_block_fields, check_pattern_total
from app.services.schedule_version import (
    published_semester_ids,
    semester_has_published_version,
)

# Task 72: every field PATCH can change. A requirement whose lessons are
# placed in a PUBLISHED or ARCHIVED version may not change any of them: the
# requirement is shared by every version of the semester, so editing it
# would leave the locked timetable inconsistent with it.
LOCKED_REQUIREMENT_FIELDS = frozenset(
    {
        "class_id",
        "subject_id",
        "semester_id",
        "weekly_periods",
        "required_teacher_id",
        "required_room_type",
        "consecutive_limit",
        # Task 87: changing the pattern regroups the lessons a locked
        # timetable already uses.
        "lesson_pattern",
    }
)


def _locked_requirement_ids_query() -> Select[tuple[int]]:
    """The one definition of "locked" (Task 56/64/72/73): ids of the
    requirements with at least one Lesson placed in a PUBLISHED or ARCHIVED
    version (fully locked, Task 25). Every check below narrows this same
    query, so the delete guard, the update guard and the is_locked response
    field can never disagree."""
    return (
        select(Lesson.class_subject_requirement_id)
        .join(Schedule, Schedule.lesson_id == Lesson.id)
        .join(ScheduleVersion, Schedule.schedule_version_id == ScheduleVersion.id)
        .where(ScheduleVersion.status.in_(LOCKED_STATUSES))
    )


def is_used_by_locked_schedule(db: Session, requirement_id: int) -> bool:
    """Whether this one requirement is locked (delete and update guards)."""
    locked_id = db.scalars(
        _locked_requirement_ids_query()
        .where(Lesson.class_subject_requirement_id == requirement_id)
        .limit(1)
    ).first()
    return locked_id is not None


def locked_requirement_ids(db: Session, requirement_ids: list[int]) -> set[int]:
    """Task 73: which of these requirements are locked -- one query for a
    whole list (the is_locked field of GET /class-subject-requirements),
    never one per requirement."""
    if not requirement_ids:
        return set()
    return set(
        db.scalars(
            _locked_requirement_ids_query()
            .where(Lesson.class_subject_requirement_id.in_(requirement_ids))
            .distinct()
        ).all()
    )


def create_class_subject_requirement(
    db: Session, requirement_data: ClassSubjectRequirementCreate
) -> ClassSubjectRequirement:
    requirement = ClassSubjectRequirement(**requirement_data.model_dump())
    db.add(requirement)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(requirement)
    return requirement


def get_class_subject_requirement(
    db: Session, requirement_id: int, *, role: str | None = None
) -> ClassSubjectRequirement | None:
    """Task 72: a TEACHER only sees a requirement whose semester currently
    has a PUBLISHED version; any other one resolves to None (the router's
    existing 404). `role=None` (ADMIN and internal callers) sees all."""
    requirement = db.get(ClassSubjectRequirement, requirement_id)
    if requirement is None:
        return None
    if role == "TEACHER" and not semester_has_published_version(
        db, requirement.semester_id
    ):
        return None
    return requirement


def get_class_subject_requirements(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    *,
    semester_id: int | None = None,
    role: str | None = None,
) -> list[ClassSubjectRequirement]:
    """Task 66: optional semester_id filter; an unknown semester simply
    matches no rows. Ordered by id so skip/limit pages are stable. Task 72:
    a TEACHER only gets requirements of semesters that currently have a
    PUBLISHED version."""
    stmt = select(ClassSubjectRequirement)
    if semester_id is not None:
        stmt = stmt.where(ClassSubjectRequirement.semester_id == semester_id)
    if role == "TEACHER":
        stmt = stmt.where(
            ClassSubjectRequirement.semester_id.in_(published_semester_ids())
        )
    stmt = stmt.order_by(ClassSubjectRequirement.id).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_class_subject_requirement(
    db: Session,
    requirement_id: int,
    requirement_data: ClassSubjectRequirementUpdate,
) -> ClassSubjectRequirement | None:
    requirement = db.get(ClassSubjectRequirement, requirement_id)
    if requirement is None:
        return None

    requested = requirement_data.model_dump(exclude_unset=True)
    # Task 72: only an actual change counts -- sending a field's current
    # value is not an edit (same rule as ScheduleVersion's locked fields).
    changed_locked_fields = sorted(
        field
        for field, value in requested.items()
        if field in LOCKED_REQUIREMENT_FIELDS and getattr(requirement, field) != value
    )
    if changed_locked_fields and is_used_by_locked_schedule(db, requirement_id):
        raise RequirementEditBlockedByPublishedScheduleError(
            f"ClassSubjectRequirement {requirement_id} cannot change "
            f"{', '.join(changed_locked_fields)}: its lessons are used by a "
            "PUBLISHED or ARCHIVED schedule version."
        )

    # Task 87: the pattern must add up to weekly_periods as they will be
    # AFTER this update -- changing either one alone can break that.
    new_weekly_periods = requested.get("weekly_periods", requirement.weekly_periods)
    new_pattern = requested.get("lesson_pattern", requirement.lesson_pattern)
    try:
        check_pattern_total(new_pattern, new_weekly_periods)
    except ValueError as exc:
        raise InvalidLessonPatternError(str(exc)) from exc
    pattern_changed = new_pattern != requirement.lesson_pattern

    for field, value in requested.items():
        setattr(requirement, field, value)

    # Task 87: existing lessons follow the new pattern right away (lessons
    # still to be generated get theirs from generate-lessons).
    if pattern_changed:
        assign_block_fields(
            list(
                db.scalars(
                    select(Lesson).where(Lesson.class_subject_requirement_id == requirement_id)
                ).all()
            ),
            new_pattern,
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(requirement)
    return requirement


def delete_class_subject_requirement(db: Session, requirement_id: int) -> bool:
    requirement = db.get(ClassSubjectRequirement, requirement_id)
    if requirement is None:
        return False

    # Task 56: Lesson rows are owned sub-resources of this requirement
    # (generate-lessons creates them FROM it -- see app/models/lesson.py),
    # not something that genuinely still needs it -- same reasoning as
    # Task 48's delete_teacher(). lessons.class_subject_requirement_id and
    # schedules.lesson_id have no ON DELETE CASCADE, so without this, any
    # requirement that had ever been expanded into lessons could never be
    # deleted at all, and there's no endpoint to delete a Lesson by hand.
    lesson_ids = list(
        db.scalars(
            select(Lesson.id).where(
                Lesson.class_subject_requirement_id == requirement_id
            )
        ).all()
    )

    # A PUBLISHED or (Task 64) ARCHIVED version is fully locked (Task 25):
    # if any of these lessons is placed in one, the whole delete is refused
    # up front, before anything is staged.
    if lesson_ids and is_used_by_locked_schedule(db, requirement_id):
        raise RequirementUsedByPublishedScheduleError(
            f"ClassSubjectRequirement {requirement_id} cannot be deleted: "
            "its lessons are used by a PUBLISHED or ARCHIVED schedule "
            "version."
        )

    # Everything below is staged on `db` but not committed yet. Each step is
    # flushed explicitly so the DELETE order is Schedule -> Lesson ->
    # requirement (child rows before the rows they reference). If any step
    # fails, the rollback() undoes the WHOLE transaction, so a lesson is
    # never lost while its requirement survives.
    try:
        if lesson_ids:
            # Only DRAFT rows can remain here (PUBLISHED/ARCHIVED was
            # refused above).
            draft_schedules = db.scalars(
                select(Schedule).where(Schedule.lesson_id.in_(lesson_ids))
            ).all()
            for schedule in draft_schedules:
                db.delete(schedule)
            db.flush()

            lessons = db.scalars(
                select(Lesson).where(Lesson.id.in_(lesson_ids))
            ).all()
            for lesson in lessons:
                db.delete(lesson)
            db.flush()

        db.delete(requirement)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"ClassSubjectRequirement {requirement_id} cannot be deleted: "
            "other records still reference it."
        ) from exc

    return True
