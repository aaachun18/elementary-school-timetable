"""Task 98: which school a scheduling record belongs to.

Six tables carry school_id themselves (the "root" tables: Teacher, Subject,
Room, AcademicYear, Grade, TimeSlot). Every other scheduling table reaches
its school through them:

    Semester            -> AcademicYear
    Class, GradeSubjectRequirement -> Grade
    ClassSubjectRequirement, ScheduleVersion -> Semester
    Lesson              -> ClassSubjectRequirement
    Schedule            -> ScheduleVersion
    TeacherSubject, TeacherAvailability -> Teacher
    SemesterTeacher, SemesterGradeTimeSlot -> Semester
    SemesterTeacherUnavailability -> SemesterTeacher

in_school() turns that chain into one SQL condition (nested IN subqueries,
no joins), so any select() can be limited to a school by adding
`.where(in_school(Model, school_id))`. Plain functions, no FastAPI: a
record outside the caller's school is simply "not found" (None) here, and
the router turns that into the usual 404.
"""

from collections.abc import Iterable
from typing import Any, TypeVar

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class, Grade
from app.models.grade_subject_requirement import GradeSubjectRequirement
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.semester_grade_time_slot import SemesterGradeTimeSlot
from app.models.semester_teacher import SemesterTeacher, SemesterTeacherUnavailability
from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherAvailability, TeacherSubject
from app.models.time_slot import TimeSlot
from app.services.exceptions import InvalidReferenceError

ModelT = TypeVar("ModelT")

ROOT_MODELS: tuple[type[Any], ...] = (Teacher, Subject, Room, AcademicYear, Grade, TimeSlot)


def in_school(model: type[Any], school_id: int) -> ColumnElement[bool]:
    """A WHERE condition: `model`'s row belongs to `school_id`."""
    if model in ROOT_MODELS:
        return model.school_id == school_id
    if model is Semester:
        return Semester.academic_year_id.in_(
            select(AcademicYear.id).where(in_school(AcademicYear, school_id))
        )
    if model in (Class, GradeSubjectRequirement):
        return model.grade_id.in_(select(Grade.id).where(in_school(Grade, school_id)))
    if model is ClassSubjectRequirement:
        return ClassSubjectRequirement.semester_id.in_(
            select(Semester.id).where(in_school(Semester, school_id))
        )
    if model is ScheduleVersion:
        return ScheduleVersion.semester_id.in_(
            select(Semester.id).where(in_school(Semester, school_id))
        )
    if model is Lesson:
        return Lesson.class_subject_requirement_id.in_(
            select(ClassSubjectRequirement.id).where(
                in_school(ClassSubjectRequirement, school_id)
            )
        )
    if model is Schedule:
        return Schedule.schedule_version_id.in_(
            select(ScheduleVersion.id).where(in_school(ScheduleVersion, school_id))
        )
    if model in (SemesterTeacher, SemesterGradeTimeSlot):
        return model.semester_id.in_(select(Semester.id).where(in_school(Semester, school_id)))
    if model is SemesterTeacherUnavailability:
        return SemesterTeacherUnavailability.semester_teacher_id.in_(
            select(SemesterTeacher.id).where(in_school(SemesterTeacher, school_id))
        )
    if model in (TeacherSubject, TeacherAvailability):
        return model.teacher_id.in_(select(Teacher.id).where(in_school(Teacher, school_id)))
    raise ValueError(f"{model.__name__} has no school scope")


def get_in_school(
    db: Session, model: type[ModelT], record_id: int, school_id: int
) -> ModelT | None:
    """The record, or None if it doesn't exist or belongs to another school."""
    stmt = select(model).where(
        model.id == record_id,  # type: ignore[attr-defined]
        in_school(model, school_id),
    )
    return db.scalars(stmt).first()


def is_in_school(db: Session, model: type[Any], record_id: int, school_id: int) -> bool:
    return get_in_school(db, model, record_id, school_id) is not None


def ensure_references_in_school(
    db: Session, school_id: int, references: Iterable[tuple[type[Any], int | None]]
) -> None:
    """Every (model, id) pair (None ids are skipped) must name a record of
    `school_id`. Otherwise InvalidReferenceError (-> 422): from inside one
    school, a record of another school is just as nonexistent as a
    deleted one."""
    for model, record_id in references:
        if record_id is not None and not is_in_school(db, model, record_id, school_id):
            raise InvalidReferenceError(
                f"{model.__name__} {record_id} does not exist in school {school_id}."
            )


def school_id_of_semester(db: Session, semester_id: int) -> int:
    school_id = db.scalar(
        select(AcademicYear.school_id)
        .join(Semester, Semester.academic_year_id == AcademicYear.id)
        .where(Semester.id == semester_id)
    )
    if school_id is None:
        raise ValueError(f"Semester {semester_id} does not exist.")
    return school_id


def school_id_of_version(db: Session, schedule_version: ScheduleVersion) -> int:
    """The school a version's whole timetable lives in -- every teacher,
    room and time slot a scheduling service may use for it must be from
    this school."""
    return school_id_of_semester(db, schedule_version.semester_id)
