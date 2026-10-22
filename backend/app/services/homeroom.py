"""導師 (homeroom teachers) of a 排課紀錄 and the subjects they teach by
default. The wizard's 教師設定 step names each class's 導師
(SemesterTeacher.homeroom_class_id); at a 國小 the 導師 also teaches the
class's 國語文 and 數學 unless the 科目需求 step says otherwise. 國中 / 高中
have no such default.

When the default applies:
- a class's 導師 is set or changed -> its 國語文 / 數學 requirements get
  the new 導師 as their teacher (whatever was chosen before);
- a class's 導師 is removed -> those requirements that still have the old
  導師 lose their teacher (left to the scheduler);
- the 科目需求 step creates a class's 國語文 / 數學 requirement -> it starts
  with the class's 導師.
A teacher picked in the 科目需求 step afterwards stays: the default only
acts on these changes, never on merely opening a step again.

Plain functions on a Session; nothing here commits.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.school import School
from app.models.semester_teacher import SemesterTeacher
from app.models.subject import Subject
from app.services.school_structure import MANDARIN, MATHEMATICS, SchoolType

HOMEROOM_SUBJECT_NAMES: dict[SchoolType, tuple[str, ...]] = {
    SchoolType.ELEMENTARY: (MANDARIN, MATHEMATICS),
    SchoolType.JUNIOR_HIGH: (),
    SchoolType.SENIOR_HIGH: (),
}


def homeroom_subject_ids(db: Session, school_id: int) -> set[int]:
    """The school's subjects a 導師 teaches by default (by name, per the
    school's type) -- empty for 國中 / 高中."""
    school = db.get(School, school_id)
    if school is None:
        return set()
    names = HOMEROOM_SUBJECT_NAMES[SchoolType(school.school_type)]
    if not names:
        return set()
    return set(
        db.scalars(
            select(Subject.id).where(Subject.school_id == school_id, Subject.name.in_(names))
        ).all()
    )


def homeroom_teachers(db: Session, version_id: int) -> dict[int, int]:
    """class_id -> its 導師's teacher_id, for the record's classes that
    have one."""
    return {
        class_id: teacher_id
        for class_id, teacher_id in db.execute(
            select(SemesterTeacher.homeroom_class_id, SemesterTeacher.teacher_id).where(
                SemesterTeacher.schedule_version_id == version_id,
                SemesterTeacher.homeroom_class_id.is_not(None),
            )
        ).all()
    }


def stage_apply_homeroom_changes(
    db: Session,
    version_id: int,
    school_id: int,
    before: dict[int, int],
    after: dict[int, int],
) -> None:
    """Staged: the record's 國語文 / 數學 requirements follow each class
    whose 導師 changed from `before` to `after` (class_id -> teacher_id);
    see the module docstring."""
    subject_ids = homeroom_subject_ids(db, school_id)
    changed_class_ids = {
        class_id
        for class_id in before.keys() | after.keys()
        if before.get(class_id) != after.get(class_id)
    }
    if not subject_ids or not changed_class_ids:
        return
    for requirement in db.scalars(
        select(ClassSubjectRequirement).where(
            ClassSubjectRequirement.schedule_version_id == version_id,
            ClassSubjectRequirement.class_id.in_(changed_class_ids),
            ClassSubjectRequirement.subject_id.in_(subject_ids),
        )
    ).all():
        new_teacher_id = after.get(requirement.class_id)
        if new_teacher_id is not None:
            requirement.required_teacher_id = new_teacher_id
        elif requirement.required_teacher_id == before.get(requirement.class_id):
            requirement.required_teacher_id = None
