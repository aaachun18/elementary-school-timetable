import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# tests/conftest.py -> parent.parent is the repo root, which holds backend/
# (the `app` package). Mirrors the same bootstrap used in
# backend/alembic/env.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(REPO_ROOT / ".env")

# Importing app.models registers every model's table on Base.metadata --
# without this, create_all()/drop_all() below would see an empty metadata
# (same pitfall as Task 2.5's alembic/env.py bug).
import app.models  # noqa: E402, F401
from app.core.security import (  # noqa: E402
    configure_bcrypt_rounds_for_testing,
    create_access_token,
    hash_password,
)
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.academic_year import AcademicYear, Semester  # noqa: E402
from app.models.grade_class import MAX_GRADE_LEVEL, MIN_GRADE_LEVEL, Grade  # noqa: E402
from app.models.schedule_version import (  # noqa: E402
    AUTO,
    COPIED,
    EDITING,
    NOT_SCHEDULED,
    ScheduleVersion,
)
from app.models.school import School  # noqa: E402
from app.models.time_slot import TimeSlot  # noqa: E402
from app.models.semester_teacher import (  # noqa: E402
    SemesterTeacher,
    SemesterTeacherUnavailability,
)
from app.models.teacher import Teacher  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import mailer  # noqa: E402
from app.services.mailer import AccountMail  # noqa: E402

# bcrypt is deliberately slow in production (that's the point). Nearly every
# test creates an admin/teacher user via the fixtures below, so at
# production cost the suite would pay that price ~100+ times over. Tests
# don't need brute-force resistance, so drop to bcrypt's minimum cost factor
# here -- this only ever touches the CryptContext instance inside this test
# process, never the deployed app.
configure_bcrypt_rounds_for_testing(4)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
DEV_DATABASE_URL = os.environ.get("DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. Add it to your local .env -- see "
        "the TEST_DATABASE_URL example in .env.example. It must point at "
        "a separate database (e.g. timetable_test), not your dev database."
    )

if DEV_DATABASE_URL and TEST_DATABASE_URL == DEV_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL must not be the same as DATABASE_URL -- this "
        "test suite calls Base.metadata.drop_all() against it, which would "
        "destroy your dev database."
    )

test_engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def sent_mails(monkeypatch: pytest.MonkeyPatch) -> list[AccountMail]:
    """帳號改版: creating an account mails its password. No test ever
    reaches a real SMTP server: every mail lands in this list instead (a
    test may replace mailer.deliver again to simulate a failure)."""
    mails: list[AccountMail] = []

    def fake_deliver(mail: AccountMail) -> bool:
        mails.append(mail)
        return True

    monkeypatch.setattr(mailer, "deliver", fake_deliver)
    return mails


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """A clean database per test: create every table before the test runs,
    drop them all afterward, so no test can depend on data left behind by
    another one."""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        username="admin_test",
        hashed_password=hash_password("admin-test-password"),
        role="ADMIN",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


TEST_SCHOOL_NAME = "帳號測試學校"


def get_test_school_id(db_session: Session) -> int:
    """Task 98: the one school every test's data and fixture accounts
    belong to, created on first use. Test builders that insert rows
    straight into the database call this for their school_id, so their
    rows are visible to the `client` fixture's 教學組長."""
    school = db_session.scalars(select(School).where(School.name == TEST_SCHOOL_NAME)).first()
    if school is None:
        school = School(name=TEST_SCHOOL_NAME, is_active=True)
        db_session.add(school)
        db_session.commit()
    return school.id


def next_free_grade_level(db_session: Session) -> int:
    """Task 98: grade levels are 1-12 and unique per school, but many test
    builders used to make up a distinct level per world (8901, 30061, ...)
    just to keep their grades apart. They now ask for the lowest level the
    test school hasn't used yet instead; a grade's name still carries the
    builder's own key."""
    used = set(
        db_session.scalars(
            select(Grade.level).where(Grade.school_id == get_test_school_id(db_session))
        ).all()
    )
    free = [level for level in range(MIN_GRADE_LEVEL, MAX_GRADE_LEVEL + 1) if level not in used]
    assert free, "the test school already has every grade level"
    return free[0]


def time_slot_at(
    db_session: Session,
    weekday: int,
    period: int,
    *,
    is_teaching_period: bool = True,
    label: str | None = None,
    school_id: int | None = None,
) -> TimeSlot:
    """A school's grid has one slot per (weekday, period) -- built with the
    school in the app, unique in the database. The test school is created
    bare (get_test_school_id), so builders add only the slots they need:
    this returns the slot already at that position (setting its
    is_teaching_period / label), or adds it. Flushed, not committed."""
    school_id = get_test_school_id(db_session) if school_id is None else school_id
    slot = db_session.scalars(
        select(TimeSlot).where(
            TimeSlot.school_id == school_id,
            TimeSlot.weekday == weekday,
            TimeSlot.period == period,
        )
    ).first()
    if slot is None:
        slot = TimeSlot(school_id=school_id, weekday=weekday, period=period)
        db_session.add(slot)
    slot.is_teaching_period = is_teaching_period
    slot.label = label
    db_session.flush()
    return slot


def make_record(
    db_session: Session,
    semester_id: int,
    *,
    status: str = NOT_SCHEDULED,
    is_published: bool = False,
    source_status: str = AUTO,
) -> ScheduleVersion:
    """v3: a 排課紀錄 of the semester for test builders that write straight
    to the database -- numbered like the app numbers them (the school's
    next 編號), in the given state (see mark_status_in_db())."""
    school_id = db_session.scalar(
        select(AcademicYear.school_id)
        .join(Semester, Semester.academic_year_id == AcademicYear.id)
        .where(Semester.id == semester_id)
    )
    assert school_id is not None, f"semester {semester_id} does not exist"
    record = ScheduleVersion(
        school_id=school_id,
        semester_id=semester_id,
        version_number=_next_number(db_session, school_id),
        status=NOT_SCHEDULED,
        is_published=False,
    )
    db_session.add(record)
    db_session.flush()
    mark_status_in_db(
        db_session, record.id, status, is_published=is_published, source_status=source_status
    )
    return record


def _next_number(db_session: Session, school_id: int) -> int:
    numbers = db_session.scalars(
        select(ScheduleVersion.version_number).where(ScheduleVersion.school_id == school_id)
    ).all()
    return max((number for number in numbers if number is not None), default=0) + 1


def mark_status_in_db(
    db_session: Session,
    schedule_version_id: int,
    status: str,
    *,
    is_published: bool = False,
    source_status: str = AUTO,
) -> None:
    """Puts a record straight into `status` (keeping its id and contents).
    EDITING (a manual edit's working copy) needs the record it edits: an
    empty record of the same semester, of `source_status`, is made for it.
    COPIED needs the number it was copied from: 1. Committed."""
    record = db_session.get(ScheduleVersion, schedule_version_id)
    assert record is not None
    # The source first, before the record changes: every check constraint
    # ties several of the record's columns together, so they all change in
    # one flush.
    source_id: int | None = None
    if status == EDITING:
        source = ScheduleVersion(
            school_id=record.school_id,
            semester_id=record.semester_id,
            version_number=_next_number(db_session, record.school_id),
            status=source_status,
            is_published=False,
            copied_from_number=1 if source_status == COPIED else None,
        )
        db_session.add(source)
        db_session.flush()
        source_id = source.id
    if status == EDITING:
        version_number = None
    elif record.version_number is None:
        version_number = _next_number(db_session, record.school_id)
    else:
        version_number = record.version_number
    record.is_published = False
    record.editing_source_id = source_id
    record.version_number = version_number
    record.copied_from_number = 1 if status == COPIED else None
    record.status = status
    db_session.flush()
    record.is_published = is_published
    db_session.commit()


def enroll_in_semester(
    db_session: Session,
    schedule_version_id: int,
    teacher: Teacher,
    *,
    min_weekly_periods: int | None = None,
    max_weekly_periods: int | None = None,
    unavailable_time_slot_ids: tuple[int, ...] = (),
) -> SemesterTeacher:
    """Task 98: makes `teacher` take part in the record's scheduling, the
    way the wizard's PUT /schedule-versions/{id}/teachers does, for test
    builders that write straight to the database (v3: settings belong to a
    record -- the name is kept from when they belonged to the semester). The weekly periods range defaults
    to the teacher's own (deprecated) Teacher.min/max_weekly_periods, so a
    builder's existing numbers keep meaning what they meant."""
    semester_teacher = SemesterTeacher(
        schedule_version_id=schedule_version_id,
        teacher_id=teacher.id,
        min_weekly_periods=(
            teacher.min_weekly_periods if min_weekly_periods is None else min_weekly_periods
        ),
        max_weekly_periods=(
            teacher.max_weekly_periods if max_weekly_periods is None else max_weekly_periods
        ),
    )
    db_session.add(semester_teacher)
    db_session.flush()
    db_session.add_all(
        SemesterTeacherUnavailability(
            semester_teacher_id=semester_teacher.id, time_slot_id=time_slot_id
        )
        for time_slot_id in unavailable_time_slot_ids
    )
    db_session.commit()
    return semester_teacher


@pytest.fixture
def account_school(db_session: Session) -> School:
    """Task 98: the school the COORDINATOR / TEACHER fixture accounts below
    belong to -- every non-ADMIN account must belong to one."""
    school = db_session.get(School, get_test_school_id(db_session))
    assert school is not None
    return school


@pytest.fixture
def coordinator_user(db_session: Session, account_school: School) -> User:
    user = User(
        username="coordinator_test",
        hashed_password=hash_password("coordinator-test-password"),
        role="COORDINATOR",
        is_active=True,
        school_id=account_school.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def teacher_user(db_session: Session, account_school: School) -> User:
    user = User(
        username="teacher_test",
        hashed_password=hash_password("teacher-test-password"),
        role="TEACHER",
        is_active=True,
        school_id=account_school.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user: User) -> str:
    return create_access_token({"sub": admin_user.username})


@pytest.fixture
def coordinator_token(coordinator_user: User) -> str:
    return create_access_token({"sub": coordinator_user.username})


@pytest.fixture
def teacher_token(teacher_user: User) -> str:
    return create_access_token({"sub": teacher_user.username})


def _make_client(
    db_session: Session, token: str | None
) -> Generator[TestClient, None, None]:
    """Shared setup for every client-like fixture below: override get_db()
    to use the test database session, and attach a bearer token (or none)
    to every request the returned TestClient makes."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        yield TestClient(app, headers=headers)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(
    db_session: Session, coordinator_token: str
) -> Generator[TestClient, None, None]:
    """Default TestClient used by nearly all existing tests. Carries a real,
    valid JWT on every request, so these tests exercise the real auth/RBAC
    dependencies rather than bypassing them -- no dependency_overrides for
    the role checks exist anywhere in this file. Task 98: it is the
    教學組長 of the test school (get_test_school_id) -- the account that
    works with scheduling data; the 系統管理員 is `admin_client`."""
    yield from _make_client(db_session, coordinator_token)


@pytest.fixture
def admin_client(db_session: Session, admin_token: str) -> Generator[TestClient, None, None]:
    """Task 98: the 系統管理員 -- schools and accounts only."""
    yield from _make_client(db_session, admin_token)


@pytest.fixture
def teacher_client(
    db_session: Session, teacher_token: str
) -> Generator[TestClient, None, None]:
    """A TestClient authenticated as a TEACHER, for verifying the read-only
    side of RBAC (can GET, cannot POST/PATCH/DELETE)."""
    yield from _make_client(db_session, teacher_token)


@pytest.fixture
def coordinator_client(
    db_session: Session, coordinator_token: str
) -> Generator[TestClient, None, None]:
    """Task 98: a TestClient authenticated as a COORDINATOR (教學組長)."""
    yield from _make_client(db_session, coordinator_token)


@pytest.fixture
def unauthenticated_client(db_session: Session) -> Generator[TestClient, None, None]:
    """A TestClient with no Authorization header at all, for verifying that
    protected endpoints reject anonymous requests."""
    yield from _make_client(db_session, None)
