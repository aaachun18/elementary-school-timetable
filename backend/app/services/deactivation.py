"""停用 (deactivating) a teacher, subject, room or class: what it would
touch, as counts for the confirmation dialog. Read only; every count is one
aggregate query (no per-row loop).

- published_records / other_records: 排課紀錄 whose TIMETABLE uses it
  (a Schedule row), split by 已發布. A manual edit's working copy
  (EDITING) is not a record of its own and is left out.
- not_scheduled_records: 尚未排課 records whose SETTINGS name it (參與教師 /
  指定老師, 指定教室 / 合併課教室, a requirement of the subject, a
  requirement / 導師 / 合併課 of the class).
- grade_requirements: the school's 年級科目需求 of the subject (subjects
  only; 0 otherwise).
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Select, func, select, union
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.combined_lesson import CombinedLesson
from app.models.grade_subject_requirement import GradeSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import EDITING, NOT_SCHEDULED, ScheduleVersion
from app.models.semester_teacher import SemesterTeacher

EntityKind = Literal["teacher", "subject", "room", "class"]


@dataclass(frozen=True)
class DeactivationImpact:
    published_records: int
    other_records: int
    not_scheduled_records: int
    grade_requirements: int


def _timetable_versions(kind: EntityKind, entity_id: int) -> Select[tuple[int]]:
    """The schedule_version_id of every Schedule row that uses the entity."""
    stmt = select(Schedule.schedule_version_id)
    if kind == "teacher":
        return stmt.where(Schedule.teacher_id == entity_id)
    if kind == "room":
        return stmt.where(Schedule.room_id == entity_id)
    stmt = stmt.join(Lesson, Schedule.lesson_id == Lesson.id).join(
        ClassSubjectRequirement,
        Lesson.class_subject_requirement_id == ClassSubjectRequirement.id,
    )
    if kind == "subject":
        return stmt.where(ClassSubjectRequirement.subject_id == entity_id)
    return stmt.where(ClassSubjectRequirement.class_id == entity_id)


def _setting_versions(kind: EntityKind, entity_id: int) -> Select[tuple[int]]:
    """The schedule_version_id of every settings row that names the entity
    (any record status; the caller narrows it down)."""
    requirement_version = select(ClassSubjectRequirement.schedule_version_id)
    if kind == "teacher":
        return union(
            select(SemesterTeacher.schedule_version_id).where(
                SemesterTeacher.teacher_id == entity_id
            ),
            requirement_version.where(
                ClassSubjectRequirement.required_teacher_id == entity_id
            ),
        ).subquery().select()
    if kind == "room":
        return union(
            requirement_version.where(ClassSubjectRequirement.required_room_id == entity_id),
            select(CombinedLesson.schedule_version_id).where(
                CombinedLesson.room_id == entity_id
            ),
        ).subquery().select()
    if kind == "subject":
        return requirement_version.where(ClassSubjectRequirement.subject_id == entity_id)
    return union(
        requirement_version.where(ClassSubjectRequirement.class_id == entity_id),
        select(SemesterTeacher.schedule_version_id).where(
            SemesterTeacher.homeroom_class_id == entity_id
        ),
        select(CombinedLesson.schedule_version_id).where(
            CombinedLesson.homeroom_class_id == entity_id
        ),
    ).subquery().select()


def deactivation_impact(db: Session, kind: EntityKind, entity_id: int) -> DeactivationImpact:
    used = _timetable_versions(kind, entity_id).subquery()
    published_by_flag = dict(
        db.execute(
            select(ScheduleVersion.is_published, func.count(func.distinct(ScheduleVersion.id)))
            .where(ScheduleVersion.id.in_(select(used.c[0])), ScheduleVersion.status != EDITING)
            .group_by(ScheduleVersion.is_published)
        )
        .tuples()
        .all()
    )

    settings = _setting_versions(kind, entity_id).subquery()
    not_scheduled = db.scalar(
        select(func.count(func.distinct(ScheduleVersion.id))).where(
            ScheduleVersion.id.in_(select(settings.c[0])),
            ScheduleVersion.status == NOT_SCHEDULED,
        )
    )

    grade_requirements = 0
    if kind == "subject":
        grade_requirements = db.scalar(
            select(func.count(GradeSubjectRequirement.id)).where(
                GradeSubjectRequirement.subject_id == entity_id
            )
        ) or 0

    return DeactivationImpact(
        published_records=published_by_flag.get(True, 0),
        other_records=published_by_flag.get(False, 0),
        not_scheduled_records=not_scheduled or 0,
        grade_requirements=grade_requirements,
    )


def class_record_count(db: Session, class_id: int) -> int:
    """How many 排課紀錄 (any status) use the class -- a requirement, a
    導師, a 合併課 -- i.e. why it can't be deleted."""
    settings = _setting_versions("class", class_id).subquery()
    return db.scalar(select(func.count(func.distinct(settings.c[0])))) or 0
