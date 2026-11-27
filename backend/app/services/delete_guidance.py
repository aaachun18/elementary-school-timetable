from collections.abc import Iterable

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.combined_lesson import CombinedLesson
from app.models.grade_class import Class, Grade
from app.models.grade_subject_requirement import GradeSubjectRequirement
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.semester_teacher import SemesterTeacher
from app.models.teacher import Teacher
from app.models.user import User

# 「此資料仍被其他資料參照，無法刪除」: what to do first, in order, so the
# delete succeeds -- shown behind the error's ? icon. Called by the
# delete_xxx() services only after the delete has failed (and been rolled
# back), so the common, successful delete never pays for these queries.
#
# Most references live inside 排課紀錄 (their settings and timetable), so
# most steps are "刪除排課紀錄編號 N". The 編號 people see shifts when a
# record is deleted (1 = the newest; deleting one renumbers every OLDER
# record), so the steps go from the oldest record to the newest -- deleting
# an older one never changes the number of a newer one still to delete.

def _semester_label(version: ScheduleVersion) -> str:
    semester = version.semester
    return f"{semester.academic_year.year} 學年度第 {semester.number} 學期"


def version_steps(db: Session, version_ids: Iterable[int]) -> list[str]:
    """The steps that remove every one of these records' references: delete
    the record (oldest first); a published record must first stop being
    the published one; a working copy (手動編輯中) is cancelled -- unless
    its own record is deleted anyway, which takes the working copy with
    it."""
    ids = set(version_ids)
    if not ids:
        return []
    versions = list(db.scalars(select(ScheduleVersion).where(ScheduleVersion.id.in_(ids))).all())
    records = {version.id: version for version in versions if version.editing_source_id is None}

    steps: list[str] = []
    for version in sorted(records.values(), key=lambda item: -(item.display_number or 0)):
        label = f"排課紀錄編號 {version.display_number}（{_semester_label(version)}）"
        if version.is_published:
            steps.append(f"{label}是目前發布中的課表，請先在排課紀錄發布同學期的另一筆紀錄")
        steps.append(f"到「排課紀錄」刪除{label}")

    for version in versions:
        source_id = version.editing_source_id
        if source_id is None or source_id in records:
            continue
        source = db.get(ScheduleVersion, source_id)
        number = source.display_number if source is not None else None
        steps.append(
            f"排課紀錄編號 {number} 正在手動編輯中，請開啟該課表並按「取消編輯」"
            "（或先「儲存課表」，再依上面的方式刪除儲存後的紀錄）"
        )
    return steps


def _versions_of_requirements(db: Session, condition: ColumnElement[bool]) -> set[int]:
    stmt = select(ClassSubjectRequirement.schedule_version_id).where(condition)
    return set(db.scalars(stmt).all())


def class_delete_steps(db: Session, class_id: int) -> list[str]:
    """A class is used by 排課紀錄: its 科目需求, its 導師, a 共同排課 held
    in its own room."""
    version_ids = _versions_of_requirements(db, ClassSubjectRequirement.class_id == class_id)
    version_ids |= set(
        db.scalars(
            select(SemesterTeacher.schedule_version_id).where(
                SemesterTeacher.homeroom_class_id == class_id
            )
        ).all()
    )
    version_ids |= set(
        db.scalars(
            select(CombinedLesson.schedule_version_id).where(
                CombinedLesson.homeroom_class_id == class_id
            )
        ).all()
    )
    return version_steps(db, version_ids)


def room_delete_steps(db: Session, room_id: int) -> list[str]:
    """A room is used by 排課紀錄: a 科目需求's special room, a placed
    lesson, a 共同排課."""
    version_ids = _versions_of_requirements(db, ClassSubjectRequirement.required_room_id == room_id)
    version_ids |= set(
        db.scalars(select(Schedule.schedule_version_id).where(Schedule.room_id == room_id)).all()
    )
    version_ids |= set(
        db.scalars(
            select(CombinedLesson.schedule_version_id).where(CombinedLesson.room_id == room_id)
        ).all()
    )
    return version_steps(db, version_ids)


def subject_delete_steps(db: Session, subject_id: int) -> list[str]:
    """A subject is used by the school's 年級科目需求 and by 排課紀錄."""
    steps: list[str] = []
    grade_names = list(
        db.scalars(
            select(Grade.name)
            .join(GradeSubjectRequirement, GradeSubjectRequirement.grade_id == Grade.id)
            .where(GradeSubjectRequirement.subject_id == subject_id)
            .order_by(Grade.level)
        ).all()
    )
    if grade_names:
        steps.append(f"到「學校資料 > 科目需求」刪除{'、'.join(grade_names)}的這個科目")
    version_ids = _versions_of_requirements(db, ClassSubjectRequirement.subject_id == subject_id)
    return steps + version_steps(db, version_ids)


def school_delete_steps(db: Session, school_id: int) -> list[str]:
    """What still belongs to the school besides the grades, time slots,
    subjects and 科目需求 delete_school() removes along with it."""
    steps: list[str] = []
    version_ids = set(
        db.scalars(
            select(ScheduleVersion.id).where(ScheduleVersion.school_id == school_id)
        ).all()
    )
    steps += version_steps(db, version_ids)

    class_count = db.scalar(
        select(func.count())
        .select_from(Class)
        .join(Grade, Grade.id == Class.grade_id)
        .where(Grade.school_id == school_id)
    )
    if class_count:
        steps.append(f"到「學校資料 > 班級」刪除這所學校的 {class_count} 個班級")
    room_count = db.scalar(select(func.count()).select_from(Room).where(Room.school_id == school_id))
    if room_count:
        steps.append(f"到「學校資料 > 教室」刪除這所學校的 {room_count} 間教室")

    teacher_count = db.scalar(
        select(func.count()).select_from(Teacher).where(Teacher.school_id == school_id)
    )
    # 帳號改版: accounts are never deleted; they move to another school.
    account_count = db.scalar(
        select(func.count()).select_from(User).where(User.school_id == school_id)
    )
    if account_count:
        steps.append(f"到「帳號管理」把這所學校的 {account_count} 個帳號改到其他學校")
    if teacher_count:
        steps.append(
            f"這所學校已有 {teacher_count} 位教師資料，教師資料無法刪除，因此這所學校目前無法刪除；"
            "不再使用的帳號請改按「停用」"
        )

    year_count = db.scalar(
        select(func.count()).select_from(AcademicYear).where(AcademicYear.school_id == school_id)
    )
    if year_count:
        steps.append(
            f"這所學校已建立 {year_count} 個學年度，學年度目前無法從畫面刪除，因此這所學校目前無法刪除"
        )
    return steps
