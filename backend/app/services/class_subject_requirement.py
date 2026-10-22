"""A 排課紀錄's class subject requirements (科目需求): how many weekly periods
a class needs of a subject, its lesson pattern, teacher and room. v3: they
belong to one record (schedule_version_id) and change only while it is
尚未排課 -- SettingsLockedError (409) otherwise, for create, update, delete
and the sync from the school's 科目需求 alike."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class
from app.models.grade_subject_requirement import GradeSubjectRequirement
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
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
    raise_for_integrity_error,
)
from app.services.homeroom import homeroom_subject_ids, homeroom_teachers
from app.services.lesson_pattern import assign_block_fields, check_pattern_total
from app.services.schedule_version import (
    lock_record_for_settings,
    published_version_ids,
    raise_if_settings_locked,
)
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)


def _ensure_references_in_school(
    db: Session, school_id: int, fields: dict[str, object]
) -> None:
    """Task 98: the record, class, subject, required teacher and required
    room a requirement points at must all be of the caller's school."""
    references: list[tuple[type, int | None]] = [
        (model, fields.get(field))  # type: ignore[misc]
        for model, field in (
            (ScheduleVersion, "schedule_version_id"),
            (Class, "class_id"),
            (Subject, "subject_id"),
            (Teacher, "required_teacher_id"),
            (Room, "required_room_id"),
        )
    ]
    ensure_references_in_school(db, school_id, references)


def _raise_if_locked(db: Session, schedule_version_id: int) -> None:
    schedule_version = db.get(ScheduleVersion, schedule_version_id)
    assert schedule_version is not None  # FK / checked by the caller
    raise_if_settings_locked(schedule_version)


def create_class_subject_requirement(
    db: Session, requirement_data: ClassSubjectRequirementCreate, *, school_id: int
) -> ClassSubjectRequirement:
    _ensure_references_in_school(db, school_id, requirement_data.model_dump())
    _raise_if_locked(db, requirement_data.schedule_version_id)
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
    """Task 72: a TEACHER only sees a requirement of a published record;
    any other one resolves to None (the router's existing 404). `role=None`
    (the 教學組長 and internal callers) sees all of the school's."""
    requirement = get_in_school(db, ClassSubjectRequirement, requirement_id, school_id)
    if requirement is None:
        return None
    if role == "TEACHER":
        schedule_version = db.get(ScheduleVersion, requirement.schedule_version_id)
        if schedule_version is None or not schedule_version.is_published:
            return None
    return requirement


def get_class_subject_requirements(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    *,
    school_id: int,
    schedule_version_id: int | None = None,
    role: str | None = None,
) -> list[ClassSubjectRequirement]:
    """Optional schedule_version_id filter; an unknown record simply
    matches no rows. Ordered by id so skip/limit pages are stable. Task 72:
    a TEACHER only gets requirements of published records."""
    stmt = select(ClassSubjectRequirement).where(
        in_school(ClassSubjectRequirement, school_id)
    )
    if schedule_version_id is not None:
        stmt = stmt.where(ClassSubjectRequirement.schedule_version_id == schedule_version_id)
    if role == "TEACHER":
        stmt = stmt.where(
            ClassSubjectRequirement.schedule_version_id.in_(published_version_ids())
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
    _raise_if_locked(db, requirement.schedule_version_id)

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
    """Staged, not committed: these lessons and any Schedule rows of them,
    flushed in that order -- child rows before the rows they reference. (A
    尚未排課 record has no timetable, so normally there are none.)"""
    if not lesson_ids:
        return
    for schedule in db.scalars(select(Schedule).where(Schedule.lesson_id.in_(lesson_ids))).all():
        db.delete(schedule)
    db.flush()
    for lesson in db.scalars(select(Lesson).where(Lesson.id.in_(lesson_ids))).all():
        db.delete(lesson)
    db.flush()


def _lesson_ids(db: Session, requirement_id: int) -> list[int]:
    return list(
        db.scalars(
            select(Lesson.id).where(Lesson.class_subject_requirement_id == requirement_id)
        ).all()
    )


def delete_class_subject_requirement(
    db: Session, requirement_id: int, *, school_id: int
) -> bool:
    """Task 56: the requirement goes with its Lesson rows -- they are its
    owned sub-resources (generate-lessons creates them from it). One
    transaction: Lesson rows first, then the requirement."""
    requirement = get_in_school(db, ClassSubjectRequirement, requirement_id, school_id)
    if requirement is None:
        return False
    _raise_if_locked(db, requirement.schedule_version_id)

    try:
        _stage_delete_lessons(db, _lesson_ids(db, requirement_id))
        db.delete(requirement)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"ClassSubjectRequirement {requirement_id} cannot be deleted: "
            "other records still reference it."
        ) from exc

    return True


# --- the school's 科目需求 -> a record (wizard 科目需求 step) ---


def _pattern_or_none(pattern: str | None, weekly_periods: int) -> str | None:
    """The pattern, if it still adds up to weekly_periods; else none."""
    try:
        check_pattern_total(pattern, weekly_periods)
    except ValueError:
        return None
    return pattern


def sync_version_requirements(
    db: Session, schedule_version_id: int, *, school_id: int
) -> RequirementSyncResult | None:
    """Makes the record's requirements follow the school's 科目需求
    (GradeSubjectRequirement), for every class of the school:
    - a grade rule a class has no requirement for -> created (no pattern
      or room yet; no teacher either, except a 國小 class's 國語文 / 數學,
      which start with the class's 導師 -- services/homeroom.py);
    - weekly_periods differing from the rule -> changed to it; a lesson
      pattern that no longer adds up is cleared, and lessons beyond the new
      count are deleted (missing ones are made by generate-lessons when
      scheduling);
    - a requirement with no rule any more -> deleted, lessons with it.
    The lesson pattern, teacher and room the wizard set are kept. Only a
    尚未排課 record (409 otherwise). All in one transaction. None if the
    record doesn't exist in the school."""
    schedule_version = get_in_school(db, ScheduleVersion, schedule_version_id, school_id)
    if schedule_version is None:
        return None
    lock_record_for_settings(db, schedule_version)

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
                ClassSubjectRequirement.schedule_version_id == schedule_version_id
            )
        ).all()
    )

    created = updated = removed = 0
    try:
        for requirement in existing:
            key = (requirement.class_id, requirement.subject_id)
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
        homerooms = homeroom_teachers(db, schedule_version_id)
        homeroom_subjects = homeroom_subject_ids(db, school_id)
        for (class_id, subject_id), weekly_periods in sorted(rule_periods.items()):
            if (class_id, subject_id) not in covered:
                db.add(
                    ClassSubjectRequirement(
                        schedule_version_id=schedule_version_id,
                        class_id=class_id,
                        subject_id=subject_id,
                        weekly_periods=weekly_periods,
                        required_teacher_id=(
                            homerooms.get(class_id) if subject_id in homeroom_subjects else None
                        ),
                    )
                )
                created += 1
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)

    return RequirementSyncResult(created=created, updated=updated, removed=removed)


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
