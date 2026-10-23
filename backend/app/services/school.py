from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.grade_class import Grade
from app.models.grade_subject_requirement import GradeSubjectRequirement
from app.models.school import School
from app.models.subject import Subject
from app.models.time_slot import TimeSlot
from app.schemas.school import SchoolCreate, SchoolUpdate
from app.services.delete_guidance import school_delete_steps
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.school_structure import (
    DEFAULT_GRADE_PERIODS,
    DEFAULT_SUBJECTS,
    GRADE_LEVELS,
    SchoolType,
    default_time_slots,
    grade_name,
)


def _add_fixed_structure(db: Session, school: School, school_type: SchoolType) -> None:
    """Staged, not committed: the grades and the weekly time slot grid a
    school of this type always has, plus (v3) its default subjects and each
    grade's weekly periods of them (app/services/school_structure.py)."""
    grades = [
        Grade(school_id=school.id, name=grade_name(level), level=level)
        for level in GRADE_LEVELS[school_type]
    ]
    subjects = {
        name: Subject(school_id=school.id, name=name, is_active=True)
        for name in DEFAULT_SUBJECTS[school_type]
    }
    db.add_all(grades)
    db.add_all(subjects.values())
    db.flush()  # the grade and subject ids the 科目需求 rows need
    periods_by_level = DEFAULT_GRADE_PERIODS[school_type]
    db.add_all(
        GradeSubjectRequirement(
            grade_id=grade.id, subject_id=subjects[subject_name].id, weekly_periods=periods
        )
        for grade in grades
        for subject_name, periods in periods_by_level.get(grade.level, ())
    )
    db.add_all(
        TimeSlot(
            school_id=school.id,
            weekday=slot.weekday,
            period=slot.period,
            is_teaching_period=slot.is_teaching_period,
            label=slot.label,
        )
        for slot in default_time_slots(school_type)
    )


def create_school(db: Session, school_data: SchoolCreate) -> School:
    """The school together with its grades, time slots and (國小) default
    subjects and 科目需求, in one transaction."""
    school = School(
        name=school_data.name, is_active=True, school_type=school_data.school_type.value
    )
    db.add(school)
    try:
        db.flush()
        _add_fixed_structure(db, school, school_data.school_type)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(school)
    return school


def get_school(db: Session, school_id: int) -> School | None:
    return db.get(School, school_id)


def get_schools(db: Session, skip: int = 0, limit: int = 100) -> list[School]:
    stmt = select(School).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_school(
    db: Session, school_id: int, school_data: SchoolUpdate
) -> School | None:
    school = db.get(School, school_id)
    if school is None:
        return None

    for field, value in school_data.model_dump(exclude_unset=True).items():
        setattr(school, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(school)
    return school


def delete_school(db: Session, school_id: int) -> bool:
    school = db.get(School, school_id)
    if school is None:
        return False

    try:
        # Its fixed grades and time slots were built with it and go with
        # it, and so do its subjects and 科目需求 (v3: a 國小 starts with
        # them); anything else still referencing them (classes, schedules
        # ...) blocks the delete like a direct reference would.
        grade_ids = select(Grade.id).where(Grade.school_id == school_id)
        db.execute(
            delete(GradeSubjectRequirement).where(GradeSubjectRequirement.grade_id.in_(grade_ids))
        )
        db.execute(delete(Grade).where(Grade.school_id == school_id))
        db.execute(delete(TimeSlot).where(TimeSlot.school_id == school_id))
        db.execute(delete(Subject).where(Subject.school_id == school_id))
        db.delete(school)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"School {school_id} cannot be deleted: other records still "
            "reference it.",
            school_delete_steps(db, school_id),
        ) from exc

    return True
