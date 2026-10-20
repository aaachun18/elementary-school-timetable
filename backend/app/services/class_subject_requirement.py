from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class
from app.models.grade_subject_requirement import GradeSubjectRequirement
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import LOCKED_STATUSES, ScheduleVersion
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.schemas.class_subject_requirement import (
    ClassSubjectRequirementCreate,
    ClassSubjectRequirementUpdate,
    RequirementSyncResult,
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
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
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
        "required_room_id",
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


def _ensure_references_in_school(
    db: Session, school_id: int, fields: dict[str, object]
) -> None:
    """Task 98: the semester, class, subject, required teacher and required
    room a requirement points at must all be of the caller's school."""
    references: list[tuple[type, int | None]] = [
        (model, fields.get(field))  # type: ignore[misc]
        for model, field in (
            (Semester, "semester_id"),
            (Class, "class_id"),
            (Subject, "subject_id"),
            (Teacher, "required_teacher_id"),
            (Room, "required_room_id"),
        )
    ]
    ensure_references_in_school(db, school_id, references)


def create_class_subject_requirement(
    db: Session, requirement_data: ClassSubjectRequirementCreate, *, school_id: int
) -> ClassSubjectRequirement:
    _ensure_references_in_school(db, school_id, requirement_data.model_dump())
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
    db: Session, requirement_id: int, *, school_id: int, role: str | None = None
) -> ClassSubjectRequirement | None:
    """Task 72: a TEACHER only sees a requirement whose semester currently
    has a PUBLISHED version; any other one resolves to None (the router's
    existing 404). `role=None` (the 教學組長 and internal callers) sees
    all of the school's."""
    requirement = get_in_school(db, ClassSubjectRequirement, requirement_id, school_id)
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
    school_id: int,
    semester_id: int | None = None,
    role: str | None = None,
) -> list[ClassSubjectRequirement]:
    """Task 66: optional semester_id filter; an unknown semester simply
    matches no rows. Ordered by id so skip/limit pages are stable. Task 72:
    a TEACHER only gets requirements of semesters that currently have a
    PUBLISHED version."""
    stmt = select(ClassSubjectRequirement).where(
        in_school(ClassSubjectRequirement, school_id)
    )
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
    *,
    school_id: int,
) -> ClassSubjectRequirement | None:
    requirement = get_in_school(db, ClassSubjectRequirement, requirement_id, school_id)
    if requirement is None:
        return None

    requested = requirement_data.model_dump(exclude_unset=True)
    _ensure_references_in_school(db, school_id, requested)
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


def _stage_delete_lessons(db: Session, lesson_ids: list[int]) -> None:
    """Staged, not committed: these lessons and their (DRAFT) Schedule rows,
    flushed in that order -- child rows before the rows they reference.
    The caller has made sure no locked version uses them."""
    if not lesson_ids:
        return
    for schedule in db.scalars(select(Schedule).where(Schedule.lesson_id.in_(lesson_ids))).all():
        db.delete(schedule)
    db.flush()
    for lesson in db.scalars(select(Lesson).where(Lesson.id.in_(lesson_ids))).all():
        db.delete(lesson)
    db.flush()


def delete_class_subject_requirement(
    db: Session, requirement_id: int, *, school_id: int
) -> bool:
    requirement = get_in_school(db, ClassSubjectRequirement, requirement_id, school_id)
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
        # Only DRAFT rows can remain here (PUBLISHED/ARCHIVED was refused
        # above).
        _stage_delete_lessons(db, lesson_ids)
        db.delete(requirement)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"ClassSubjectRequirement {requirement_id} cannot be deleted: "
            "other records still reference it."
        ) from exc

    return True


# --- the school's 科目需求 -> a semester (wizard 科目需求 step) ---


def _pattern_or_none(pattern: str | None, weekly_periods: int) -> str | None:
    """The pattern, if it still adds up to weekly_periods; else none."""
    try:
        check_pattern_total(pattern, weekly_periods)
    except ValueError:
        return None
    return pattern


def sync_semester_requirements(
    db: Session, semester_id: int, *, school_id: int
) -> RequirementSyncResult | None:
    """Makes the semester's requirements follow the school's 科目需求
    (GradeSubjectRequirement), for every class of the school:
    - a grade rule a class has no requirement for -> created (no pattern,
      teacher or room yet);
    - weekly_periods differing from the rule -> changed to it; a lesson
      pattern that no longer adds up is cleared, and lessons beyond the new
      count are deleted with their DRAFT schedules (missing ones are made
      by generate-lessons when scheduling);
    - a requirement with no rule any more -> deleted, lessons and DRAFT
      schedules with it.
    A requirement a PUBLISHED or ARCHIVED version uses is never touched
    (listed in locked_requirement_ids). The lesson pattern, teacher and
    room the wizard set are kept. All in one transaction. None if the
    semester doesn't exist in the school."""
    if get_in_school(db, Semester, semester_id, school_id) is None:
        return None

    rule_periods = {
        (class_id, subject_id): weekly_periods
        for class_id, subject_id, weekly_periods in db.execute(
            select(
                Class.id,
                GradeSubjectRequirement.subject_id,
                GradeSubjectRequirement.weekly_periods,
            )
            .join(GradeSubjectRequirement, GradeSubjectRequirement.grade_id == Class.grade_id)
            .where(in_school(Class, school_id))
        ).all()
    }
    existing = list(
        db.scalars(
            select(ClassSubjectRequirement).where(
                ClassSubjectRequirement.semester_id == semester_id
            )
        ).all()
    )
    locked_ids = locked_requirement_ids(db, [requirement.id for requirement in existing])

    created = updated = removed = 0
    try:
        for requirement in existing:
            key = (requirement.class_id, requirement.subject_id)
            if requirement.id in locked_ids:
                continue
            if key not in rule_periods:
                _stage_delete_lessons(db, _lesson_ids(db, requirement.id))
                db.delete(requirement)
                removed += 1
                continue
            weekly_periods = rule_periods[key]
            if requirement.weekly_periods != weekly_periods:
                _resize(db, requirement, weekly_periods)
                updated += 1

        covered = {(requirement.class_id, requirement.subject_id) for requirement in existing}
        for (class_id, subject_id), weekly_periods in sorted(rule_periods.items()):
            if (class_id, subject_id) not in covered:
                db.add(
                    ClassSubjectRequirement(
                        semester_id=semester_id,
                        class_id=class_id,
                        subject_id=subject_id,
                        weekly_periods=weekly_periods,
                    )
                )
                created += 1
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)

    return RequirementSyncResult(
        created=created,
        updated=updated,
        removed=removed,
        locked_requirement_ids=sorted(locked_ids),
    )


def _lesson_ids(db: Session, requirement_id: int) -> list[int]:
    return list(
        db.scalars(
            select(Lesson.id).where(Lesson.class_subject_requirement_id == requirement_id)
        ).all()
    )


def _resize(db: Session, requirement: ClassSubjectRequirement, weekly_periods: int) -> None:
    """Staged: the requirement's new weekly periods, its pattern cleared if
    it no longer adds up, lessons beyond the new count deleted and the rest
    regrouped by the (possibly cleared) pattern."""
    requirement.weekly_periods = weekly_periods
    requirement.lesson_pattern = _pattern_or_none(requirement.lesson_pattern, weekly_periods)
    lessons = list(
        db.scalars(
            select(Lesson)
            .where(Lesson.class_subject_requirement_id == requirement.id)
            .order_by(Lesson.sequence_number)
        ).all()
    )
    _stage_delete_lessons(db, [lesson.id for lesson in lessons[weekly_periods:]])
    assign_block_fields(lessons[:weekly_periods], requirement.lesson_pattern)
