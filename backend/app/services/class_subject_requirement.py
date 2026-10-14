from sqlalchemy import select
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
    RequirementUsedByPublishedScheduleError,
    raise_for_integrity_error,
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
    db: Session, requirement_id: int
) -> ClassSubjectRequirement | None:
    return db.get(ClassSubjectRequirement, requirement_id)


def get_class_subject_requirements(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    *,
    semester_id: int | None = None,
) -> list[ClassSubjectRequirement]:
    """Task 66: optional semester_id filter; an unknown semester simply
    matches no rows. Ordered by id so skip/limit pages are stable."""
    stmt = select(ClassSubjectRequirement)
    if semester_id is not None:
        stmt = stmt.where(ClassSubjectRequirement.semester_id == semester_id)
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

    for field, value in requirement_data.model_dump(exclude_unset=True).items():
        setattr(requirement, field, value)

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

    if lesson_ids:
        # A PUBLISHED or (Task 64) ARCHIVED version is fully locked
        # (Task 25): if any of these lessons is placed in one, the whole
        # delete is refused up front, before anything is staged.
        published_schedule_id = db.scalars(
            select(Schedule.id)
            .join(ScheduleVersion, Schedule.schedule_version_id == ScheduleVersion.id)
            .where(
                Schedule.lesson_id.in_(lesson_ids),
                ScheduleVersion.status.in_(LOCKED_STATUSES),
            )
            .limit(1)
        ).first()
        if published_schedule_id is not None:
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
