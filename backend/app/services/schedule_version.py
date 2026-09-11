from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule_version import ScheduleVersion
from app.schemas.schedule_version import ScheduleVersionCreate, ScheduleVersionUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    LessonOverProvisionedError,
    PublishedVersionImmutableError,
    raise_for_integrity_error,
)

# --- Standard CRUD ---


def create_schedule_version(
    db: Session, version_data: ScheduleVersionCreate
) -> ScheduleVersion:
    schedule_version = ScheduleVersion(
        semester_id=version_data.semester_id,
        version_number=version_data.version_number,
        status=version_data.status,
    )
    db.add(schedule_version)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(schedule_version)
    return schedule_version


def get_schedule_version(
    db: Session, schedule_version_id: int
) -> ScheduleVersion | None:
    return db.get(ScheduleVersion, schedule_version_id)


def get_schedule_versions(
    db: Session, skip: int = 0, limit: int = 100
) -> list[ScheduleVersion]:
    stmt = select(ScheduleVersion).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_schedule_version(
    db: Session, schedule_version_id: int, version_data: ScheduleVersionUpdate
) -> ScheduleVersion | None:
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None

    if schedule_version.status == "PUBLISHED":
        # Task 25: a PUBLISHED version is fully locked -- including
        # changing status itself (e.g. back to DRAFT). The only sanctioned
        # way to change anything is to clone a new DRAFT version first
        # (not yet implemented).
        raise PublishedVersionImmutableError(
            f"ScheduleVersion {schedule_version_id} is PUBLISHED and "
            "cannot be modified."
        )

    for field, value in version_data.model_dump(exclude_unset=True).items():
        setattr(schedule_version, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(schedule_version)
    return schedule_version


def delete_schedule_version(db: Session, schedule_version_id: int) -> bool:
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return False

    try:
        db.delete(schedule_version)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"ScheduleVersion {schedule_version_id} cannot be deleted: "
            "other records still reference it."
        ) from exc

    return True


# --- generate-lessons: diff-sync Lesson rows against the semester's
# ClassSubjectRequirement list (Lesson is version-independent -- see
# app/models/lesson.py -- so this really operates on the ScheduleVersion's
# *semester*, not the version itself; any version in the same semester
# would see/produce the same Lesson rows). ---


def generate_lessons(
    db: Session, schedule_version_id: int
) -> list[Lesson] | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).

    Otherwise, for every ClassSubjectRequirement in the version's semester:
    - fewer existing Lesson rows than weekly_periods -> create the missing
      ones (sequence numbers continue from the current count).
    - more existing Lesson rows than weekly_periods -> collected as an
      over-provisioning error.

    If ANY requirement is over-provisioned, the whole call is aborted --
    nothing is created for ANY requirement, not even the ones that were
    fine -- and LessonOverProvisionedError is raised with the full list of
    offending requirements. Otherwise, all missing lessons are created in
    one commit and returned (possibly an empty list if everything was
    already in sync).
    """
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None

    if schedule_version.status == "PUBLISHED":
        raise PublishedVersionImmutableError(
            f"ScheduleVersion {schedule_version_id} is PUBLISHED and "
            "cannot be modified."
        )

    requirements = list(
        db.scalars(
            select(ClassSubjectRequirement).where(
                ClassSubjectRequirement.semester_id == schedule_version.semester_id
            )
        ).all()
    )

    over_provisioned: list[dict[str, int]] = []
    to_create: list[tuple[int, int]] = []  # (class_subject_requirement_id, sequence_number)

    for requirement in requirements:
        existing_count = (
            db.scalar(
                select(func.count())
                .select_from(Lesson)
                .where(
                    Lesson.class_subject_requirement_id == requirement.id
                )
            )
            or 0
        )

        if existing_count > requirement.weekly_periods:
            over_provisioned.append(
                {
                    "class_subject_requirement_id": requirement.id,
                    "weekly_periods": requirement.weekly_periods,
                    "existing_lesson_count": existing_count,
                }
            )
        elif existing_count < requirement.weekly_periods:
            for sequence_number in range(
                existing_count + 1, requirement.weekly_periods + 1
            ):
                to_create.append((requirement.id, sequence_number))

    if over_provisioned:
        raise LessonOverProvisionedError(over_provisioned)

    created: list[Lesson] = []
    for class_subject_requirement_id, sequence_number in to_create:
        lesson = Lesson(
            class_subject_requirement_id=class_subject_requirement_id,
            sequence_number=sequence_number,
        )
        db.add(lesson)
        created.append(lesson)

    if created:
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise_for_integrity_error(exc)
        for lesson in created:
            db.refresh(lesson)

    return created
