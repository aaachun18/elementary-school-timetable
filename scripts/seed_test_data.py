"""Seed a demo school for the scheduling wizard (v3).

Creates, in the dev database (DATABASE_URL), one complete, schedulable
school -- the same data a 教學組長 would enter through 開始排課:

- the school 示範國小 and its accounts: a 系統管理員 (only when the
  database has none yet), a 教學組長 and ten 一般老師 (each account
  creates its Teacher);
- what a new 國小 is built with: grades 一年級 to 六年級, the Monday-Friday
  time slots (0 早自習 / 5 午休 / 9 放學 not schedulable), the ten default
  subjects and every grade's weekly periods of them (學校資料 > 科目需求);
- 115 學年度第 1 學期, two special rooms (自然教室, 藝術教室) -- every other
  lesson is taught in the class's own room (原班上課, no room);
- one class per grade (一年甲班 ...);
- one 排課紀錄 (尚未排課) with its settings: every teacher takes part
  (8-20 periods a week, a few unavailable slots), every grade open for its
  default slots, and the requirements synced from the school's 科目需求 the
  way the wizard does, then given their teacher (國語文 by the class's own
  teacher), special room and lesson pattern; its lessons are generated --
  and, with --run, the scheduler run on it (成功 -> 自動排課).

Like before, the script calls app.services.* directly (the same functions
the routers call, so the same validation) and never imports app.main.

It refuses to run twice: if 示範國小 already exists it stops. Dev data is
disposable -- reset the database to start over, e.g.
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
from app.schemas.room import RoomCreate  # noqa: E402
from app.schemas.schedule_version import ScheduleVersionCreate  # noqa: E402
from app.schemas.school import SchoolCreate  # noqa: E402
from app.schemas.semester import SemesterCreate  # noqa: E402
from app.schemas.semester_settings import SemesterTeacherEntry, SemesterTeachersUpdate  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.schemas.user import AccountCreate  # noqa: E402
from app.services import academic_year as academic_year_service  # noqa: E402
from app.services import class_ as class_service  # noqa: E402
from app.services import class_subject_requirement as requirement_service  # noqa: E402
from app.services import grade as grade_service  # noqa: E402
from app.services import room as room_service  # noqa: E402
from app.services import schedule_version as schedule_version_service  # noqa: E402
from app.services import scheduler as scheduler_service  # noqa: E402
from app.services import school as school_service  # noqa: E402
from app.services import semester as semester_service  # noqa: E402
from app.services import semester_settings as settings_service  # noqa: E402
from app.services import subject as subject_service  # noqa: E402
from app.services import time_slot as time_slot_service  # noqa: E402
from app.services.school_structure import (  # noqa: E402
    ARTS,
    MANDARIN,
    NATURAL_SCIENCE,
    ClassNameStyle,
    SchoolType,
    class_name_options,
)
from app.services import profile as profile_service  # noqa: E402
from app.services import user as user_service  # noqa: E402

SCHOOL_NAME = "示範國小"
PASSWORD = "demo-pass-123"
ADMIN_USERNAME = "admin"
# 帳號改版: 教學組長 / 一般老師 accounts are emails (example.com is
# reserved for examples, so no real mailbox is ever written to).
COORDINATOR_USERNAME = "coordinator@example.com"
COORDINATOR_NAME = "林組長"
TEACHER_EMAIL_DOMAIN = "example.com"
ACADEMIC_YEAR = 115
SEMESTER_NUMBER = 1
# The class's own teacher (導師) teaches its 國語文: teacher index per class.
TEACHER_NAMES = [
    "王老師", "林老師", "陳老師", "李老師", "張老師",
    "吳老師", "黃老師", "劉老師", "蔡老師", "楊老師",
]
NATURE_ROOM = "自然教室"
ARTS_ROOM = "藝術教室"
MIN_WEEKLY_PERIODS = 8
MAX_WEEKLY_PERIODS = 20


@dataclass(frozen=True)
class RequirementSetup:
    """What the wizard's 科目需求 step adds to a synced requirement."""

    lesson_pattern: str | None = None
    special_room: str | None = None
    homeroom_teacher: bool = False


# By subject name; subjects not listed keep no pattern, teacher or room.
# Patterns are left out where the weekly periods vary by grade.
SETUPS = {
    MANDARIN: RequirementSetup(homeroom_teacher=True),
    NATURAL_SCIENCE: RequirementSetup("2+1", special_room=NATURE_ROOM),
    ARTS: RequirementSetup("2+1", special_room=ARTS_ROOM),
}


def _redacted_url() -> str:
    url = get_settings().database_url
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    credentials, host = rest.split("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def _set_demo_password(db: Session, user_id: int) -> None:
    """New accounts get a random password (mailed -- here: written to the
    log); the demo accounts all share PASSWORD instead."""
    user = db.get(User, user_id)
    assert user is not None
    user.hashed_password = hash_password(PASSWORD)
    db.commit()


def _accounts(db: Session, school_id: int) -> tuple[User, list[Teacher]]:
    admin = db.scalars(select(User).where(User.role == ADMIN)).first()
    if admin is None:
        admin = user_service.create_bootstrap_admin(db, ADMIN_USERNAME, PASSWORD)
        print(f"系統管理員：{ADMIN_USERNAME} / {PASSWORD}")
    created = user_service.create_account(
        db, AccountCreate(email=COORDINATOR_USERNAME, school_id=school_id), admin
    )
    _set_demo_password(db, created.user.id)
    coordinator = db.get(User, created.user.id)
    assert coordinator is not None
    profile_service.update_name(db, coordinator, COORDINATOR_NAME)

    teachers: list[Teacher] = []
    for index, name in enumerate(TEACHER_NAMES, start=1):
        created = user_service.create_account(
            db,
            AccountCreate(email=f"teacher{index:02d}@{TEACHER_EMAIL_DOMAIN}", teacher_name=name),
            coordinator,
        )
        _set_demo_password(db, created.user.id)
        teacher = user_service.current_teacher_of(db, created.user.id)
        assert teacher is not None
        teachers.append(teacher)
    print(
        f"教學組長：{COORDINATOR_USERNAME} / {PASSWORD}；一般老師："
        f"teacher01@{TEACHER_EMAIL_DOMAIN}-teacher{len(TEACHER_NAMES):02d}@{TEACHER_EMAIL_DOMAIN}"
        f" / {PASSWORD}"
    )
    return coordinator, teachers


def seed(db: Session, *, run: bool) -> None:
    if db.scalars(select(School).where(School.name == SCHOOL_NAME)).first() is not None:
        raise SystemExit(f"「{SCHOOL_NAME}」已經存在，不重複建立。要重來請先重設開發資料庫。")

    # A new 國小 comes with its grades, time slots, default subjects and
    # every grade's weekly periods of them.
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
    special_rooms = {
        name: room_service.create_room(db, RoomCreate(name=name), school_id=school_id)
        for name in (NATURE_ROOM, ARTS_ROOM)
    }
    subject_name_of = {
        subject.id: subject.name
        for subject in subject_service.get_subjects(db, limit=1000, school_id=school_id)
    }

    grades = grade_service.get_grades(db, school_id=school_id)
    classes = [
        class_service.create_class(
            db,
            ClassCreate(
                grade_id=grade.id,
                name_style=ClassNameStyle.HEAVENLY_STEM,
                name=class_name_options(grade.level, ClassNameStyle.HEAVENLY_STEM)[0],
            ),
            school_id=school_id,
        )
        for grade in grades
    ]

    # The 排課紀錄 the wizard would create, and its settings.
    record = schedule_version_service.create_schedule_version(
        db, ScheduleVersionCreate(semester_id=semester.id), school_id=school_id
    )
    for grade in grades:
        defaults = settings_service.default_grade_time_slots(db, grade.id, school_id=school_id)
        assert defaults is not None
        settings_service.replace_grade_time_slots(db, record.id, grade.id, defaults, school_id=school_id)

    # Every teacher takes part; two of them can't teach on Monday morning.
    monday_morning = [slots[(1, period)].id for period in (1, 2)]
    settings_service.replace_semester_teachers(
        db,
        record.id,
        SemesterTeachersUpdate(
            teachers=[
                SemesterTeacherEntry(
                    teacher_id=teacher.id,
                    min_weekly_periods=MIN_WEEKLY_PERIODS,
                    max_weekly_periods=MAX_WEEKLY_PERIODS,
                    unavailable_time_slot_ids=monday_morning if index in (8, 9) else [],
                )
                for index, teacher in enumerate(teachers)
            ]
        ),
        school_id=school_id,
    )

    requirement_service.sync_version_requirements(db, record.id, school_id=school_id)
    homeroom_teacher_of_class = {class_.id: teacher for class_, teacher in zip(classes, teachers)}
    lesson_count = 0
    for requirement in requirement_service.get_class_subject_requirements(
        db, limit=1000, school_id=school_id, schedule_version_id=record.id
    ):
        setup = SETUPS.get(subject_name_of[requirement.subject_id], RequirementSetup())
        requirement_service.update_class_subject_requirement(
            db,
            requirement.id,
            ClassSubjectRequirementUpdate(
                lesson_pattern=setup.lesson_pattern,
                required_teacher_id=(
                    homeroom_teacher_of_class[requirement.class_id].id
                    if setup.homeroom_teacher
                    else None
                ),
                required_room_id=(
                    special_rooms[setup.special_room].id if setup.special_room is not None else None
                ),
            ),
            school_id=school_id,
        )
        lesson_count += requirement.weekly_periods

    schedule_version_service.generate_lessons(db, record.id)
    print(
        f"{SCHOOL_NAME}：{ACADEMIC_YEAR} 學年度第 {SEMESTER_NUMBER} 學期，"
        f"{len(classes)} 個班級、{len(teachers)} 位老師、{lesson_count} 堂課，"
        f"排課紀錄編號 {record.version_number}（尚未排課）已建立。"
    )

    if run:
        outcome = scheduler_service.run_scheduler(db, record.id)
        assert outcome is not None
        if outcome.search_result is not None and outcome.search_result.success:
            print("自動排課成功，可以用教學組長帳號到「排課紀錄」查看。")
        else:
            print("自動排課沒有成功，請用教學組長帳號到「排課紀錄」檢視排課設定、修正後再自動排課。")


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
