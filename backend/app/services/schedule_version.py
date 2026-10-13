from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import (
    ARCHIVED,
    DRAFT,
    LOCKED_STATUSES,
    PUBLISHED,
    ScheduleVersion,
)
from app.schemas.schedule_version import ScheduleVersionCreate, ScheduleVersionUpdate
from app.services.exceptions import (
    ArchivedVersionImmutableError,
    DependentRecordsExistError,
    InvalidStatusTransitionError,
    LessonOverProvisionedError,
    PublishedVersionImmutableError,
    raise_for_integrity_error,
)

# Task 64: the only status changes allowed (an unchanged status is a
# separate no-op case). Publishing always archives the semester's current
# PUBLISHED version in the same transaction -- see _publish(). Task 65:
# PUBLISHED -> ARCHIVED is "unpublish" -- the semester is then left with no
# PUBLISHED version at all, which is a valid state.
ALLOWED_STATUS_TRANSITIONS = frozenset(
    {(DRAFT, PUBLISHED), (ARCHIVED, PUBLISHED), (PUBLISHED, ARCHIVED)}
)


def raise_if_version_locked(schedule_version: ScheduleVersion) -> None:
    """Task 25/64: a PUBLISHED or ARCHIVED version is fully locked -- its
    fields, its Schedule rows, generate-lessons, run-scheduler, reassigning
    a teacher, and deleting it. Shared by every service that modifies a
    version or anything under it, so the two statuses can never drift
    apart. The two exceptions differ only in the message the user sees."""
    if schedule_version.status == PUBLISHED:
        raise PublishedVersionImmutableError(
            f"ScheduleVersion {schedule_version.id} is PUBLISHED and "
            "cannot be modified."
        )
    if schedule_version.status == ARCHIVED:
        raise ArchivedVersionImmutableError(
            f"ScheduleVersion {schedule_version.id} is ARCHIVED and "
            "cannot be modified."
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
    db: Session, schedule_version_id: int, *, role: str | None = None
) -> ScheduleVersion | None:
    """Task 43: a TEACHER may only ever see a PUBLISHED ScheduleVersion --
    a DRAFT one's id resolves to None for them, exactly like it not
    existing at all. This is deliberately not a separate 403: a role that
    can't see a draft's contents has no reason to be told one exists at
    that id either, and the router already turns None into a plain 404
    for the "doesn't exist" case, so TEACHER gets that same response for
    both. `role=None` (every other caller -- ADMIN requests, and any
    internal call that doesn't pass it) sees every version, unfiltered.
    """
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None
    # Task 64: ARCHIVED is hidden from a TEACHER exactly like DRAFT.
    if role == "TEACHER" and schedule_version.status != PUBLISHED:
        return None
    return schedule_version


def get_schedule_versions(
    db: Session, skip: int = 0, limit: int = 100, *, role: str | None = None
) -> list[ScheduleVersion]:
    stmt = select(ScheduleVersion)
    if role == "TEACHER":
        stmt = stmt.where(ScheduleVersion.status == PUBLISHED)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def _changed_fields(
    schedule_version: ScheduleVersion, version_data: ScheduleVersionUpdate
) -> dict[str, object]:
    """Non-status fields in the request whose value actually differs from
    the stored one (sending a field's current value is not a change)."""
    requested = version_data.model_dump(exclude_unset=True)
    requested.pop("status", None)
    return {
        field: value
        for field, value in requested.items()
        if getattr(schedule_version, field) != value
    }


def _mark_published(schedule_version: ScheduleVersion) -> None:
    """The publish step itself -- its own function so tests can make
    exactly this last step fail and verify the rollback."""
    schedule_version.status = PUBLISHED


def _publish(db: Session, schedule_version: ScheduleVersion) -> None:
    """Archives the semester's current PUBLISHED version (if any) and then
    publishes this one, staged on `db` (the caller commits). The archive is
    flushed first: the partial unique index allows only one PUBLISHED per
    semester at any moment, so the old one must stop being PUBLISHED before
    the new one starts."""
    current_published = db.scalars(
        select(ScheduleVersion).where(
            ScheduleVersion.semester_id == schedule_version.semester_id,
            ScheduleVersion.status == PUBLISHED,
            ScheduleVersion.id != schedule_version.id,
        )
    ).all()
    for version in current_published:
        version.status = ARCHIVED
    db.flush()
    _mark_published(schedule_version)


def update_schedule_version(
    db: Session, schedule_version_id: int, version_data: ScheduleVersionUpdate
) -> ScheduleVersion | None:
    """Task 64 status rules (see ALLOWED_STATUS_TRANSITIONS):
    - unchanged status: a no-op for the status, other versions untouched;
    - DRAFT/ARCHIVED -> PUBLISHED: the semester's current PUBLISHED version
      (if any) becomes ARCHIVED in the same transaction;
    - PUBLISHED -> ARCHIVED (Task 65, unpublish): only this version changes;
      the semester then has no PUBLISHED version;
    - any other change: InvalidStatusTransitionError, nothing changes.
    A PUBLISHED/ARCHIVED version's other fields can never change
    (raise_if_version_locked). Everything is one transaction: a failure
    never leaves the old version archived without the new one published.
    """
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None

    current_status = schedule_version.status
    new_status = version_data.status or current_status
    changed_fields = _changed_fields(schedule_version, version_data)

    if current_status in LOCKED_STATUSES and changed_fields:
        raise_if_version_locked(schedule_version)
    if (
        new_status != current_status
        and (current_status, new_status) not in ALLOWED_STATUS_TRANSITIONS
    ):
        raise InvalidStatusTransitionError(
            f"ScheduleVersion {schedule_version_id} cannot change status from "
            f"{current_status} to {new_status}."
        )

    try:
        # Only a DRAFT can reach here with changed fields (checked above).
        for field, value in changed_fields.items():
            setattr(schedule_version, field, value)
        if new_status == PUBLISHED and current_status != PUBLISHED:
            _publish(db, schedule_version)
        elif new_status != current_status:
            # Unpublish (PUBLISHED -> ARCHIVED) -- the only other allowed
            # transition; no other version is affected.
            schedule_version.status = new_status
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    except Exception:
        # Not swallowed: re-raised after undoing everything staged so far,
        # so an archived old version is never left without a new one.
        db.rollback()
        raise
    db.refresh(schedule_version)
    return schedule_version


def delete_schedule_version(db: Session, schedule_version_id: int) -> bool:
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return False

    # Task 25's existing lock: a PUBLISHED version is fully immutable,
    # including deletion -- same stance update_schedule_version() already
    # takes, raised before touching anything (no point staging Schedule
    # deletes for a version that can never actually be deleted). Task 64:
    # an ARCHIVED one too -- it is kept as history.
    raise_if_version_locked(schedule_version)

    # Task 50: Schedule is a semantic sub-resource of ScheduleVersion (a
    # row only means anything within the version it was placed under --
    # see app/models/schedule.py), and schedules.schedule_version_id has
    # no ON DELETE CASCADE, so without this ANY DRAFT version that ever
    # had a Schedule row (e.g. from a completed run-scheduler call) could
    # never be deleted at all.
    #
    # Staged on `db` but not committed yet -- if the final commit() below
    # somehow still fails (no other FK currently points at
    # schedule_versions.id, but this stays defensive in case one is added
    # later), the rollback() undoes the whole transaction, including these
    # deletes, so no Schedule row is lost on a failed delete attempt.
    schedules = db.scalars(
        select(Schedule).where(Schedule.schedule_version_id == schedule_version_id)
    ).all()
    for schedule in schedules:
        db.delete(schedule)

    db.delete(schedule_version)
    try:
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
) -> tuple[list[Lesson], int] | None:
    """Returns None if the ScheduleVersion doesn't exist (caller -> 404).

    Otherwise, for every ClassSubjectRequirement in the version's semester:
    - fewer existing Lesson rows than weekly_periods -> create the missing
      ones (sequence numbers continue from the current count).
    - more existing Lesson rows than weekly_periods -> collected as an
      over-provisioning error.

    If ANY requirement is over-provisioned, the whole call is aborted --
    nothing is created for ANY requirement, not even the ones that were
    fine -- and LessonOverProvisionedError is raised with the full list of
    offending requirements. Otherwise, returns a
    (newly_created_lessons, total_lesson_count) pair: the first element is
    only what THIS call inserted (empty if everything was already in
    sync -- diff-sync is idempotent by design); the second is the actual
    total the semester has once this call returns, computed as
    sum(weekly_periods) across its requirements -- which is guaranteed
    correct at this point precisely because reaching here means nothing
    was over-provisioned, so every requirement's Lesson count now equals
    its weekly_periods exactly (see Task 32.8: a frontend page conflating
    "newly created this call" with "current total" produced a visibly
    contradictory pair of numbers on screen -- the fix is exposing the
    total explicitly rather than making the caller infer it).

    Task 28: "the excess" for an over-provisioned requirement is defined as
    the Lesson rows with the highest sequence_number, beyond weekly_periods
    many -- the same ones that would be the natural candidates to delete if
    this function ever grew auto-cleanup. Any of those specific rows that
    already has a manually-set fixed_time_slot_id is flagged in the raised
    error (never silently dropped, never silently kept without a flag): a
    human fixed that lesson to a specific slot on purpose, so it must never
    be treated as disposable just because its sequence_number happens to be
    high.
    """
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None

    raise_if_version_locked(schedule_version)

    requirements = list(
        db.scalars(
            select(ClassSubjectRequirement).where(
                ClassSubjectRequirement.semester_id == schedule_version.semester_id
            )
        ).all()
    )

    over_provisioned: list[dict[str, int | bool | list[int]]] = []
    to_create: list[tuple[int, int]] = []  # (class_subject_requirement_id, sequence_number)

    for requirement in requirements:
        existing_lessons = list(
            db.scalars(
                select(Lesson)
                .where(Lesson.class_subject_requirement_id == requirement.id)
                .order_by(Lesson.sequence_number)
            ).all()
        )
        existing_count = len(existing_lessons)

        if existing_count > requirement.weekly_periods:
            excess_count = existing_count - requirement.weekly_periods
            # Highest sequence_number first -- the natural "extra" ones.
            excess_lessons = existing_lessons[-excess_count:]
            fixed_excess_lesson_ids = [
                lesson.id
                for lesson in excess_lessons
                if lesson.fixed_time_slot_id is not None
            ]
            over_provisioned.append(
                {
                    "class_subject_requirement_id": requirement.id,
                    "weekly_periods": requirement.weekly_periods,
                    "existing_lesson_count": existing_count,
                    "includes_fixed_lesson": bool(fixed_excess_lesson_ids),
                    "fixed_lesson_ids": fixed_excess_lesson_ids,
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

    total_lesson_count = sum(requirement.weekly_periods for requirement in requirements)
    return created, total_lesson_count
