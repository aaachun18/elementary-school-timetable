"""Seed a demo school for the scheduling wizard (Task 98 rewrite).

Creates, in the dev database (DATABASE_URL), one complete, schedulable
school -- the same data a 教學組長 would enter through 開始排課:

- the school 示範國小 and its accounts: a 系統管理員 (only when the
  database has none yet), a 教學組長 and eight 一般老師 (each account
  creates its Teacher);
- 115 學年度第 1 學期; the 國小 time slots and grades (一年級 to 六年級)
  the school is built with (Monday-Friday periods 0-9; 0 / 5 / 9 not
  schedulable);
- subjects and the two special rooms (音樂教室, 自然教室) -- every other
  lesson is taught in the class's own room (原班上課, no room);
- one class per grade (一年甲班 ...);
- the school's 科目需求 per grade;
- the semester's settings: every teacher takes part (8-20 periods a week,
  a few unavailable slots), every grade open for its band's default slots;
- the semester's requirements, synced from the school's 科目需求 the way
  the wizard does, then given their teacher (國語 by the class's own
  teacher), special room and a few lesson patterns;
- a DRAFT schedule version with its lessons generated -- and, with --run,
  the scheduler run on it.

Like before, the script calls app.services.* directly (the same functions
the routers call, so the same validation) and never imports app.main.

It refuses to run twice: if 示範國小 already exists it stops. Dev data is
disposable (Task 98 decision) -- reset the database to start over, e.g.
`alembic downgrade base && alembic upgrade head`.

Usage:
    python scripts/seed_test_data.py          # seed
    python scripts/seed_test_data.py --run    # seed, then run the scheduler
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

# scripts/seed_test_data.py -> parent.parent is the repo root, which holds
# backend/ (the `app` package). Same cross-directory import bootstrap as
# backend/alembic/env.py and tests/conftest.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import get_session_local  # noqa: E402
from app.models.school import School  # noqa: E402
from app.models.teacher import Teacher  # noqa: E402
from app.models.user import ADMIN, User  # noqa: E402
from app.schemas.academic_year import AcademicYearCreate  # noqa: E402
from app.schemas.class_ import ClassCreate  # noqa: E402
from app.schemas.class_subject_requirement import ClassSubjectRequirementUpdate  # noqa: E402
from app.schemas.grade_subject_requirement import GradeSubjectRequirementCreate  # noqa: E402
from app.schemas.room import RoomCreate  # noqa: E402
from app.schemas.schedule_version import ScheduleVersionCreate  # noqa: E402
from app.schemas.school import SchoolCreate  # noqa: E402
from app.schemas.semester import SemesterCreate  # noqa: E402
from app.schemas.semester_settings import SemesterTeacherEntry, SemesterTeachersUpdate  # noqa: E402
from app.schemas.subject import SubjectCreate  # noqa: E402
from app.schemas.user import UserCreate  # noqa: E402
from app.services import academic_year as academic_year_service  # noqa: E402
from app.services import class_ as class_service  # noqa: E402
from app.services import class_subject_requirement as requirement_service  # noqa: E402
from app.services import grade as grade_service  # noqa: E402
from app.services import grade_subject_requirement as grade_requirement_service  # noqa: E402
from app.services import room as room_service  # noqa: E402
from app.services import schedule_version as schedule_version_service  # noqa: E402
from app.services import scheduler as scheduler_service  # noqa: E402
from app.services import school as school_service  # noqa: E402
from app.services import semester as semester_service  # noqa: E402
from app.services import semester_settings as settings_service  # noqa: E402
from app.services import subject as subject_service  # noqa: E402
from app.services import time_slot as time_slot_service  # noqa: E402
from app.services.school_structure import ClassNameStyle, SchoolType, class_name_options  # noqa: E402
from app.services import user as user_service  # noqa: E402
from app.services.grade_levels import grade_band  # noqa: E402

SCHOOL_NAME = "示範國小"
PASSWORD = "demo-pass-123"
ADMIN_USERNAME = "admin"
COORDINATOR_USERNAME = "coordinator"
ACADEMIC_YEAR = 115
SEMESTER_NUMBER = 1
# The class's own teacher (導師) teaches its 國語: teacher index per class.
TEACHER_NAMES = ["王老師", "林老師", "陳老師", "李老師", "張老師", "吳老師", "黃老師", "劉老師"]
SUBJECT_NAMES = ["國語", "數學", "英語", "自然", "社會", "體育", "美勞", "音樂"]
SPECIAL_ROOMS = ["音樂教室", "自然教室"]
MIN_WEEKLY_PERIODS = 8
MAX_WEEKLY_PERIODS = 20


@dataclass(frozen=True)
class RequirementSpec:
    subject: str
    weekly_periods: int
    lesson_pattern: str | None = None
    special_room: str | None = None
    homeroom_teacher: bool = False


LOWER_REQUIREMENTS = [
    RequirementSpec("國語", 6, "2+1+1+1+1", homeroom_teacher=True),
    RequirementSpec("數學", 4),
    RequirementSpec("體育", 2),
    RequirementSpec("美勞", 2, "2"),
    RequirementSpec("音樂", 2, special_room="音樂教室"),
]
UPPER_REQUIREMENTS = [
    RequirementSpec("國語", 5, homeroom_teacher=True),
    RequirementSpec("數學", 4),
    RequirementSpec("英語", 2),
    RequirementSpec("自然", 3, "2+1", special_room="自然教室"),
    RequirementSpec("社會", 2),
    RequirementSpec("體育", 2),
    RequirementSpec("美勞", 2, "2"),
    RequirementSpec("音樂", 1, special_room="音樂教室"),
]


def _specs(level: int) -> list[RequirementSpec]:
    return LOWER_REQUIREMENTS if grade_band(level).value == "LOWER" else UPPER_REQUIREMENTS


def _redacted_url() -> str:
    url = get_settings().database_url
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    credentials, host = rest.split("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def _accounts(db: Session, school_id: int) -> tuple[User, list[Teacher]]:
    admin = db.scalars(select(User).where(User.role == ADMIN)).first()
    if admin is None:
        admin = user_service.create_user(
            db, UserCreate(username=ADMIN_USERNAME, password=PASSWORD, role="ADMIN")
        )
        print(f"系統管理員：{ADMIN_USERNAME} / {PASSWORD}")
    coordinator = user_service.create_user(
        db,
        UserCreate(
            username=COORDINATOR_USERNAME, password=PASSWORD, role="COORDINATOR", school_id=school_id
        ),
        admin,
    )
    teachers: list[Teacher] = []
    for index, name in enumerate(TEACHER_NAMES, start=1):
        account = user_service.create_user(
            db,
            UserCreate(
                username=f"teacher{index:02d}",
                password=PASSWORD,
                role="TEACHER",
                teacher_name=name,
            ),
            coordinator,
        )
        teacher = db.scalars(select(Teacher).where(Teacher.user_id == account.id)).one()
        teachers.append(teacher)
    print(f"教學組長：{COORDINATOR_USERNAME} / {PASSWORD}；一般老師：teacher01-teacher{len(TEACHER_NAMES):02d} / {PASSWORD}")
    return coordinator, teachers


def seed(db: Session, *, run: bool) -> None:
    if db.scalars(select(School).where(School.name == SCHOOL_NAME)).first() is not None:
        raise SystemExit(f"「{SCHOOL_NAME}」已經存在，不重複建立。要重來請先重設開發資料庫。")

    school = school_service.create_school(
        db, SchoolCreate(name=SCHOOL_NAME, school_type=SchoolType.ELEMENTARY)
    )
    school_id = school.id
    _, teachers = _accounts(db, school_id)

    year = academic_year_service.create_academic_year(
        db, AcademicYearCreate(year=ACADEMIC_YEAR), school_id=school_id
    )
    semester = semester_service.create_semester(
        db, SemesterCreate(academic_year_id=year.id, number=SEMESTER_NUMBER), school_id=school_id
    )
    slots = {
        (slot.weekday, slot.period): slot
        for slot in time_slot_service.get_time_slots(db, limit=1000, school_id=school_id)
    }
    subjects = {
        name: subject_service.create_subject(db, SubjectCreate(name=name), school_id=school_id)
        for name in SUBJECT_NAMES
    }
    special_rooms = {
        name: room_service.create_room(db, RoomCreate(name=name), school_id=school_id)
        for name in SPECIAL_ROOMS
    }

    grades = grade_service.get_grades(db, school_id=school_id)
    classes = []
    for grade in grades:
        classes.append(
            class_service.create_class(
                db,
                ClassCreate(
                    grade_id=grade.id,
                    name_style=ClassNameStyle.HEAVENLY_STEM,
                    name=class_name_options(grade.level, ClassNameStyle.HEAVENLY_STEM)[0],
                ),
                school_id=school_id,
            )
        )
        for spec in _specs(grade.level):
            grade_requirement_service.create_grade_subject_requirement(
                db,
                GradeSubjectRequirementCreate(
                    grade_id=grade.id,
                    subject_id=subjects[spec.subject].id,
                    weekly_periods=spec.weekly_periods,
                ),
                school_id=school_id,
            )
        defaults = settings_service.default_grade_time_slots(db, grade.id, school_id=school_id)
        assert defaults is not None
        settings_service.replace_grade_time_slots(db, semester.id, grade.id, defaults, school_id=school_id)

    # Every teacher takes part; two of them can't teach on Monday morning.
    monday_morning = [slots[(1, period)].id for period in (0, 1, 2)]
    settings_service.replace_semester_teachers(
        db,
        semester.id,
        SemesterTeachersUpdate(
            teachers=[
                SemesterTeacherEntry(
                    teacher_id=teacher.id,
                    min_weekly_periods=MIN_WEEKLY_PERIODS,
                    max_weekly_periods=MAX_WEEKLY_PERIODS,
                    unavailable_time_slot_ids=monday_morning if index in (6, 7) else [],
                )
                for index, teacher in enumerate(teachers)
            ]
        ),
        school_id=school_id,
    )

    requirement_service.sync_semester_requirements(db, semester.id, school_id=school_id)
    level_of_class = {class_.id: grade.level for class_, grade in zip(classes, grades)}
    homeroom_teacher_of_class = {class_.id: teacher for class_, teacher in zip(classes, teachers)}
    subject_name_of = {subject.id: name for name, subject in subjects.items()}
    lesson_count = 0
    for requirement in requirement_service.get_class_subject_requirements(
        db, limit=1000, school_id=school_id, semester_id=semester.id
    ):
        spec = next(
            spec
            for spec in _specs(level_of_class[requirement.class_id])
            if spec.subject == subject_name_of[requirement.subject_id]
        )
        requirement_service.update_class_subject_requirement(
            db,
            requirement.id,
            ClassSubjectRequirementUpdate(
                lesson_pattern=spec.lesson_pattern,
                required_teacher_id=(
                    homeroom_teacher_of_class[requirement.class_id].id
                    if spec.homeroom_teacher
                    else None
                ),
                required_room_id=(
                    special_rooms[spec.special_room].id if spec.special_room is not None else None
                ),
            ),
            school_id=school_id,
        )
        lesson_count += spec.weekly_periods

    version = schedule_version_service.create_schedule_version(
        db,
        ScheduleVersionCreate(semester_id=semester.id, version_number=1),
        school_id=school_id,
    )
    schedule_version_service.generate_lessons(db, version.id)
    print(
        f"{SCHOOL_NAME}：{ACADEMIC_YEAR} 學年度第 {SEMESTER_NUMBER} 學期，"
        f"{len(classes)} 個班級、{len(teachers)} 位老師、{lesson_count} 堂課，草稿紀錄 v1 已建立。"
    )

    if run:
        outcome = scheduler_service.run_scheduler(db, version.id)
        assert outcome is not None
        if outcome.search_result is not None and outcome.search_result.success:
            print("自動排課成功，可以用教學組長帳號到「排課紀錄」查看。")
        else:
            print("自動排課沒有成功，請用教學組長帳號到「開始排課」的最後一步重新排課查看原因。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="store_true", help="seed, then run the scheduler")
    args = parser.parse_args()

    print(f"資料庫：{_redacted_url()}")
    session = get_session_local()()
    try:
        seed(session, run=args.run)
    finally:
        session.close()


if __name__ == "__main__":
    main()
