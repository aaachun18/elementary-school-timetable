"""v3: 排課紀錄 (ScheduleVersion) -- creating, listing, the 備註, publishing,
deleting, and the two locks every other service checks:

- settings (teachers, grade slots, requirements, lessons) change only while
  the record is 尚未排課 (NOT_SCHEDULED);
- a timetable (Schedule rows) changes only in a manual edit's working copy
  (EDITING) -- services/manual_edit.py.

Copying lives in services/schedule_copy.py, running the scheduler in
services/scheduler.py.
"""

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule_version import (
    EDITING,
    NOT_SCHEDULED,
    TIMETABLE_STATUSES,
    ScheduleVersion,
)
from app.schemas.schedule_version import ScheduleVersionCreate, ScheduleVersionUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    LessonOverProvisionedError,
    PublishedVersionDeleteError,
    RecordStatusError,
    SettingsLockedError,
    TimetableLockedError,
    raise_for_integrity_error,
)
from app.services.lesson_pattern import assign_block_fields, block_positions
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)
from app.services.version_contents import stage_delete_contents

PUBLISH_WITHOUT_TIMETABLE_MESSAGE = "這筆排課紀錄還沒有課表，無法發布"

# --- the two locks ---


def lock_record_for_settings(db: Session, schedule_version: ScheduleVersion) -> None:
    """Re-reads the record with a row lock (SELECT ... FOR UPDATE) held until
    the transaction ends, then checks it is still 尚未排課. A settings write
    that replaces rows (delete + insert, or the requirement sync) calls this
    first: two such requests for the same record -- e.g. the wizard step
    opened twice at once -- then run one after the other, the second seeing
    what the first committed, instead of both inserting the same rows and
    one failing on the unique constraint."""
    db.refresh(schedule_version, with_for_update=True)
    raise_if_settings_locked(schedule_version)


def raise_if_settings_locked(schedule_version: ScheduleVersion) -> None:
    """Settings change only while the record is 尚未排課."""
    if schedule_version.status != NOT_SCHEDULED:
        raise SettingsLockedError(
            f"ScheduleVersion {schedule_version.id} is {schedule_version.status}; "
            "only a NOT_SCHEDULED record's settings can change."
        )


def raise_if_timetable_locked(schedule_version: ScheduleVersion) -> None:
    """A timetable changes only in a manual edit's working copy."""
    if schedule_version.status != EDITING:
        raise TimetableLockedError(
            f"ScheduleVersion {schedule_version.id} is {schedule_version.status}; "
            "only an EDITING working copy's timetable can change."
        )


def settings_locked_for_requirement(db: Session, requirement: ClassSubjectRequirement) -> bool:
    """Whether the requirement's record no longer takes settings changes
    (ClassSubjectRequirementRead.is_locked)."""
    schedule_version = db.get(ScheduleVersion, requirement.schedule_version_id)
    return schedule_version is None or schedule_version.status != NOT_SCHEDULED


# --- numbers ---


def next_version_number(db: Session, school_id: int) -> int:
    """The school's next 編號: one past the highest ever given that still
    exists. Numbers are never handed out to working copies."""
    current_max = db.scalar(
        select(func.max(ScheduleVersion.version_number)).where(
            ScheduleVersion.school_id == school_id
        )
    )
    return 1 if current_max is None else current_max + 1


def stage_move_to_newest(db: Session, schedule_version: ScheduleVersion) -> None:
    """Staged, not committed: the record becomes the school's newest -- the
    next serial and a fresh 建立時間 -- so 排課紀錄 lists it first with 編號 1.
    Used when a 尚未排課 record gets its timetable: the record was made when
    the wizard started, but what people look for is when it was scheduled.
    Copies pointing at its old serial follow it (copied_from_number), so
    「複製自編號 x」 still names this record."""
    old_number = schedule_version.version_number
    new_number = next_version_number(db, schedule_version.school_id)
    if old_number is not None and old_number + 1 != new_number:
        for copy in db.scalars(
            select(ScheduleVersion).where(
                ScheduleVersion.school_id == schedule_version.school_id,
                ScheduleVersion.copied_from_number == old_number,
            )
        ).all():
            copy.copied_from_number = new_number
        schedule_version.version_number = new_number
    schedule_version.created_at = func.now()


# --- standard CRUD ---


def create_schedule_version(
    db: Session, version_data: ScheduleVersionCreate, *, school_id: int
) -> ScheduleVersion:
    """A new 尚未排課 record with no settings yet (開始排課 fills them)."""
    ensure_references_in_school(db, school_id, [(Semester, version_data.semester_id)])
    schedule_version = ScheduleVersion(
        school_id=school_id,
        semester_id=version_data.semester_id,
        version_number=next_version_number(db, school_id),
        status=NOT_SCHEDULED,
        is_published=False,
    )
    db.add(schedule_version)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(schedule_version)
    return schedule_version


def published_version_ids() -> Select[tuple[int]]:
    """Ids of the published records -- the only ones a TEACHER may read,
    together with everything under them (requirements, lessons, Schedule
    rows). A subquery: `.where(column.in_(published_version_ids()))`."""
    return select(ScheduleVersion.id).where(ScheduleVersion.is_published.is_(True))


def get_schedule_version(
    db: Session, schedule_version_id: int, *, school_id: int, role: str | None = None
) -> ScheduleVersion | None:
    """Task 43: a TEACHER only ever sees a published record -- any other
    id resolves to None for them, exactly like it not existing (the router
    turns that into the same 404). `role=None` (the 教學組長 and internal
    callers) sees every record of the school, working copies included. A
    record of another school is None too."""
    schedule_version = get_in_school(db, ScheduleVersion, schedule_version_id, school_id)
    if schedule_version is None:
        return None
    if role == "TEACHER" and not schedule_version.is_published:
        return None
    return schedule_version


def get_schedule_versions(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    *,
    school_id: int,
    role: str | None = None,
) -> list[ScheduleVersion]:
    """排課紀錄: newest first (by 編號). Working copies are never listed; a
    TEACHER only gets the published ones."""
    stmt = select(ScheduleVersion).where(
        in_school(ScheduleVersion, school_id), ScheduleVersion.status != EDITING
    )
    if role == "TEACHER":
        stmt = stmt.where(ScheduleVersion.is_published.is_(True))
    stmt = stmt.order_by(ScheduleVersion.version_number.desc()).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_schedule_version(
    db: Session,
    schedule_version_id: int,
    version_data: ScheduleVersionUpdate,
    *,
    school_id: int,
) -> ScheduleVersion | None:
    """Only the 備註 changes -- on any record, published ones included: it
    describes the record, it is not part of its timetable. Task 103: and
    the furthest 開始排課 step reached, which only ever goes up (a lower
    value -- e.g. from a stale tab -- leaves it as it is)."""
    schedule_version = get_in_school(db, ScheduleVersion, schedule_version_id, school_id)
    if schedule_version is None:
        return None
    if "note" in version_data.model_fields_set:
        schedule_version.note = version_data.note
    requested_step = version_data.wizard_furthest_step
    if requested_step is not None:
        current_step = schedule_version.wizard_furthest_step
        schedule_version.wizard_furthest_step = (
            requested_step if current_step is None else max(current_step, requested_step)
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(schedule_version)
    return schedule_version


def _mark_published(schedule_version: ScheduleVersion) -> None:
    """The publish step itself -- its own function so tests can make
    exactly this last step fail and verify the rollback."""
    schedule_version.is_published = True


def publish_schedule_version(
    db: Session, schedule_version_id: int, *, school_id: int
) -> ScheduleVersion | None:
    """發布此課表: the record becomes the semester's one published record;
    the one published before it (if any) goes back to being an ordinary
    record of its own status. Only a record with a timetable (自動排課 /
    手動排課 / 複製) can be published. One transaction: a failure never
    leaves the semester without its old published record. Publishing the
    published record again changes nothing."""
    schedule_version = get_in_school(db, ScheduleVersion, schedule_version_id, school_id)
    if schedule_version is None:
        return None
    if schedule_version.status not in TIMETABLE_STATUSES:
        raise RecordStatusError(PUBLISH_WITHOUT_TIMETABLE_MESSAGE)
    if schedule_version.is_published:
        return schedule_version

    try:
        for previous in db.scalars(
            select(ScheduleVersion).where(
                ScheduleVersion.semester_id == schedule_version.semester_id,
                ScheduleVersion.is_published.is_(True),
            )
        ).all():
            previous.is_published = False
        # The partial unique index allows one published record per semester
        # at any moment: the old one stops before the new one starts.
        db.flush()
        _mark_published(schedule_version)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    except Exception:
        # Not swallowed: re-raised after undoing everything staged so far.
        db.rollback()
        raise
    db.refresh(schedule_version)
    return schedule_version


def delete_schedule_version(
    db: Session, schedule_version_id: int, *, school_id: int
) -> bool:
    """Deletes the record with everything it owns (its settings and
    timetable, services/version_contents.py) and any working copy editing
    it. The published record cannot be deleted. One transaction."""
    schedule_version = get_in_school(db, ScheduleVersion, schedule_version_id, school_id)
    if schedule_version is None:
        return False
    if schedule_version.is_published:
        raise PublishedVersionDeleteError(
            f"ScheduleVersion {schedule_version_id} is published and cannot be deleted."
        )

    try:
        working_copies = db.scalars(
            select(ScheduleVersion).where(
                ScheduleVersion.editing_source_id == schedule_version_id
            )
        ).all()
        for working_copy in working_copies:
            stage_delete_contents(db, working_copy.id)
            db.delete(working_copy)
        db.flush()
        stage_delete_contents(db, schedule_version_id)
        db.delete(schedule_version)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"ScheduleVersion {schedule_version_id} cannot be deleted: "
            "other records still reference it."
        ) from exc
    except Exception:
        # Not swallowed: one transaction -- any other failure undoes the
        # staged deletes too before re-raising.
        db.rollback()
        raise
    return True


# --- generate-lessons: diff-sync the record's Lesson rows against its
# requirements ---


def generate_lessons(
    db: Session, schedule_version_id: int
) -> tuple[list[Lesson], int] | None:
    """Returns None if the record doesn't exist (caller -> 404). Only a
    尚未排課 record's lessons change (SettingsLockedError otherwise).

    For every requirement of the record:
    - fewer existing Lesson rows than weekly_periods -> create the missing
      ones (sequence numbers continue from the current count).
    - more existing Lesson rows than weekly_periods -> collected as an
      over-provisioning error.

    If ANY requirement is over-provisioned, the whole call is aborted --
    nothing is created for ANY requirement -- and LessonOverProvisionedError
    is raised with the full list of offending requirements. Otherwise,
    returns (newly_created_lessons, total_lesson_count): the first is only
    what THIS call inserted (empty if everything was already in sync --
    diff-sync is idempotent by design); the second the record's actual
    total, sum(weekly_periods) across its requirements (Task 32.8: a page
    once confused the two).

    Task 28: "the excess" for an over-provisioned requirement is the Lesson
    rows with the highest sequence_number beyond weekly_periods; any of
    them with a manually set fixed_time_slot_id is flagged in the error --
    a lesson fixed on purpose is never treated as disposable.
    """
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    if schedule_version is None:
        return None
    # Two calls at once (e.g. the 固定時段 dialog opened twice) would both
    # count the same existing lessons and insert the same ones -- the
    # second failing on the unique constraint. The row lock runs them one
    # after the other; the second then finds nothing left to create.
    lock_record_for_settings(db, schedule_version)

    requirements = list(
        db.scalars(
            select(ClassSubjectRequirement).where(
                ClassSubjectRequirement.schedule_version_id == schedule_version_id
            )
        ).all()
    )

    over_provisioned: list[dict[str, int | bool | list[int]]] = []
    to_create: list[tuple[int, int]] = []  # (class_subject_requirement_id, sequence_number)
    # Task 87: existing lessons whose block fields were brought in line with
    # their requirement's lesson_pattern (saved with the new lessons).
    regrouped = False
    pattern_by_requirement = {
        requirement.id: requirement.lesson_pattern for requirement in requirements
    }

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
            excess_lessons = existing_lessons[requirement.weekly_periods:]
            fixed_excess_lesson_ids = [
                lesson.id for lesson in excess_lessons if lesson.fixed_time_slot_id is not None
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
        else:
            for sequence_number in range(existing_count + 1, requirement.weekly_periods + 1):
                to_create.append((requirement.id, sequence_number))
            # Task 87: re-syncing is part of the same diff-sync -- an
            # existing lesson's block follows the pattern as it is now.
            if assign_block_fields(existing_lessons, requirement.lesson_pattern):
                regrouped = True

    if over_provisioned:
        db.rollback()  # undo any block re-sync staged above
        raise LessonOverProvisionedError(over_provisioned)

    created: list[Lesson] = []
    for class_subject_requirement_id, sequence_number in to_create:
        # Task 87: (block_no, block_seq) of this sequence number in the
        # requirement's pattern; both None without a pattern.
        block_no, block_seq = block_positions(
            pattern_by_requirement[class_subject_requirement_id], sequence_number
        )[sequence_number - 1]
        lesson = Lesson(
            class_subject_requirement_id=class_subject_requirement_id,
            sequence_number=sequence_number,
            block_no=block_no,
            block_seq=block_seq,
        )
        db.add(lesson)
        created.append(lesson)

    if created or regrouped:
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise_for_integrity_error(exc)
        for lesson in created:
            db.refresh(lesson)

    total_lesson_count = sum(requirement.weekly_periods for requirement in requirements)
    return created, total_lesson_count
