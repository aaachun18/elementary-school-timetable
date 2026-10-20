from collections.abc import Generator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class, Grade
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.school import School
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.time_slot import TimeSlot
from app.models.user import User
from tests.conftest import _make_client, enroll_in_semester, get_test_school_id, time_slot_at

# Task 98: every school's scheduling data is its own. The `client` fixture
# is the 教學組長 of the test school ("school A" below); `other_client` is
# the 教學組長 of a second school B. The 系統管理員 (`admin_client`) only
# manages schools and accounts -- every scheduling endpoint refuses it.

URL = "/api/v1/schedule-versions"


@pytest.fixture
def other_school(db_session: Session) -> School:
    school = School(name="別的學校", is_active=True)
    db_session.add(school)
    db_session.commit()
    db_session.refresh(school)
    return school


@pytest.fixture
def other_client(
    db_session: Session, other_school: School
) -> Generator[TestClient, None, None]:
    user = User(
        username="other_coordinator",
        hashed_password=hash_password("other-coordinator-pass"),
        role="COORDINATOR",
        is_active=True,
        school_id=other_school.id,
    )
    db_session.add(user)
    db_session.commit()
    yield from _make_client(db_session, create_access_token({"sub": user.username}))


@dataclass
class SchoolWorld:
    """One school's smallest schedulable semester, written straight to the
    database: one class needing 2 periods of one subject, two time slots,
    one teacher taking part in the semester."""

    year: AcademicYear
    semester: Semester
    grade: Grade
    class_: Class
    subject: Subject
    teacher: Teacher
    slots: list[TimeSlot]
    requirement: ClassSubjectRequirement
    version: ScheduleVersion


def _school_world(db: Session, school_id: int, teacher_name: str = "甲老師") -> SchoolWorld:
    year = AcademicYear(school_id=school_id, year=115, is_active=True)
    grade = Grade(school_id=school_id, name="四年級", level=4)
    subject = Subject(school_id=school_id, name="國語", is_active=True)
    teacher = Teacher(
        school_id=school_id,
        name=teacher_name,
        is_active=True,
        min_weekly_periods=0,
        max_weekly_periods=10,
    )
    slots = [
        time_slot_at(db, 1, period, is_teaching_period=True, school_id=school_id)
        for period in (1, 2)
    ]
    db.add_all([year, grade, subject, teacher, *slots])
    db.flush()
    semester = Semester(academic_year_id=year.id, number=1, is_active=True)
    class_ = Class(grade_id=grade.id, name="四年甲班")
    db.add_all([semester, class_])
    db.flush()
    enroll_in_semester(db, semester.id, teacher)
    requirement = ClassSubjectRequirement(
        semester_id=semester.id, class_id=class_.id, subject_id=subject.id, weekly_periods=2
    )
    version = ScheduleVersion(semester_id=semester.id, version_number=1, status="DRAFT")
    db.add_all([requirement, version])
    db.commit()
    return SchoolWorld(year, semester, grade, class_, subject, teacher, slots, requirement, version)


# --- the 系統管理員 has no scheduling data ---


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/subjects/"),
        ("post", "/api/v1/subjects/"),
        ("get", "/api/v1/teachers/"),
        ("get", "/api/v1/schedule-versions/"),
        ("get", "/api/v1/class-subject-requirements/"),
        ("get", "/api/v1/schedules/"),
    ],
)
def test_admin_cannot_use_scheduling_endpoints(
    admin_client: TestClient, method: str, path: str
) -> None:
    response = admin_client.request(method, path, json={"name": "國語"})

    assert response.status_code == 403


def test_admin_still_manages_schools(admin_client: TestClient) -> None:
    response = admin_client.post("/api/v1/schools/", json={"name": "新學校"})

    assert response.status_code == 201


def test_teacher_cannot_write_scheduling_data(teacher_client: TestClient) -> None:
    response = teacher_client.post("/api/v1/subjects/", json={"name": "國語"})

    assert response.status_code == 403
    assert response.json()["detail"] == "This action requires COORDINATOR role"


# --- reading and writing only one's own school ---


def test_lists_show_only_own_school(
    client: TestClient, other_client: TestClient
) -> None:
    client.post("/api/v1/subjects/", json={"name": "國語"})
    other_client.post("/api/v1/subjects/", json={"name": "數學"})

    assert [s["name"] for s in client.get("/api/v1/subjects/").json()] == ["國語"]
    assert [s["name"] for s in other_client.get("/api/v1/subjects/").json()] == ["數學"]


def test_other_schools_record_is_not_found(
    client: TestClient, other_client: TestClient
) -> None:
    subject_id = other_client.post("/api/v1/subjects/", json={"name": "數學"}).json()["id"]

    assert client.get(f"/api/v1/subjects/{subject_id}").status_code == 404
    assert client.patch(f"/api/v1/subjects/{subject_id}", json={"name": "改"}).status_code == 404
    assert client.delete(f"/api/v1/subjects/{subject_id}").status_code == 404
    assert other_client.get(f"/api/v1/subjects/{subject_id}").json()["name"] == "數學"


def test_same_names_allowed_in_different_schools(
    client: TestClient, other_client: TestClient
) -> None:
    for c in (client, other_client):
        assert c.post("/api/v1/subjects/", json={"name": "國語"}).status_code == 201
        assert c.post("/api/v1/academic-years/", json={"year": 115}).status_code == 201


def test_same_name_still_unique_within_a_school(client: TestClient) -> None:
    assert client.post("/api/v1/subjects/", json={"name": "國語"}).status_code == 201

    assert client.post("/api/v1/subjects/", json={"name": "國語"}).status_code == 409


def test_cannot_reference_other_schools_record(
    client: TestClient, db_session: Session, other_school: School
) -> None:
    other_grade = Grade(school_id=other_school.id, name="一年級", level=1)
    db_session.add(other_grade)
    db_session.commit()

    response = client.post(
        "/api/v1/classes/",
        json={"grade_id": other_grade.id, "name_style": "HEAVENLY_STEM", "name": "一年甲班"},
    )

    assert response.status_code == 422


def test_requirement_cannot_use_other_schools_teacher(
    client: TestClient, other_client: TestClient, db_session: Session, other_school: School
) -> None:
    world = _school_world(db_session, get_test_school_id(db_session))
    other = _school_world(db_session, other_school.id, teacher_name="乙老師")

    response = client.patch(
        f"/api/v1/class-subject-requirements/{world.requirement.id}",
        json={"required_teacher_id": other.teacher.id},
    )

    assert response.status_code == 422


def test_teacher_account_lists_own_school_teachers_only(
    teacher_client: TestClient, db_session: Session, other_school: School
) -> None:
    _school_world(db_session, get_test_school_id(db_session))
    _school_world(db_session, other_school.id, teacher_name="乙老師")

    names = [t["name"] for t in teacher_client.get("/api/v1/teachers/").json()]

    assert names == ["甲老師"]


# --- schedule versions ---


def test_other_schools_version_is_not_found(
    client: TestClient, db_session: Session, other_school: School
) -> None:
    other = _school_world(db_session, other_school.id)
    version_id = other.version.id

    assert client.get(f"{URL}/{version_id}").status_code == 404
    assert client.post(f"{URL}/{version_id}/generate-lessons").status_code == 404
    assert client.post(f"{URL}/{version_id}/run-scheduler").status_code == 404
    assert client.get(f"{URL}/{version_id}/check").status_code == 404
    assert client.get(f"{URL}/{version_id}/unscheduled-lessons").status_code == 404
    assert [v["id"] for v in client.get(f"{URL}/").json()] == []


def test_teacher_does_not_see_other_schools_published_version(
    teacher_client: TestClient, db_session: Session, other_school: School
) -> None:
    other = _school_world(db_session, other_school.id)
    other.version.status = "PUBLISHED"
    db_session.commit()

    assert teacher_client.get(f"{URL}/").json() == []
    assert teacher_client.get(f"{URL}/{other.version.id}").status_code == 404


def test_scheduler_uses_only_own_schools_teachers(
    client: TestClient, db_session: Session, other_school: School
) -> None:
    # School B's teacher is created first (lower id) and -- through a row
    # written straight to the database, which the API would refuse -- even
    # takes part in school A's semester. The scheduler must still only ever
    # use school A's own teacher.
    other = _school_world(db_session, other_school.id, teacher_name="乙老師")
    world = _school_world(db_session, get_test_school_id(db_session))
    enroll_in_semester(db_session, world.semester.id, other.teacher)

    assert client.post(f"{URL}/{world.version.id}/generate-lessons").status_code == 200
    response = client.post(f"{URL}/{world.version.id}/run-scheduler")

    assert response.status_code == 200, response.json()
    rows = db_session.scalars(
        select(Schedule).where(Schedule.schedule_version_id == world.version.id)
    ).all()
    assert len(rows) == 2
    assert {row.teacher_id for row in rows} == {world.teacher.id}
    assert {row.time_slot_id for row in rows} == {slot.id for slot in world.slots}


def test_scheduler_does_not_borrow_other_schools_time_slots(
    client: TestClient, db_session: Session, other_school: School
) -> None:
    # School A has only one time slot for a 2-period requirement; school B's
    # slots must not make it schedulable.
    _school_world(db_session, other_school.id, teacher_name="乙老師")
    world = _school_world(db_session, get_test_school_id(db_session))
    db_session.delete(world.slots[1])
    db_session.commit()

    client.post(f"{URL}/{world.version.id}/generate-lessons")
    response = client.post(f"{URL}/{world.version.id}/run-scheduler")

    assert response.status_code == 422
    assert db_session.scalars(
        select(Schedule).where(Schedule.schedule_version_id == world.version.id)
    ).all() == []
