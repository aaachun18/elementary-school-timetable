"""Task 98: shared test helpers for the two ways a teacher reaches a
schedule now -- an 一般老師 account (which creates its Teacher), and taking
part in a 排課紀錄's scheduling (SemesterTeacher, with the record's weekly
periods range and unavailable slots; v3: settings belong to one record).
`client` is the test school's 教學組長."""

from collections.abc import Iterable
from itertools import count

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models.grade_class import Class, Grade
from tests.conftest import (
    get_test_school_id,
    mark_status_in_db,
    next_free_grade_level,
    time_slot_at,
)

_usernames = count(1)


def create_teacher(client: TestClient, name: str) -> int:
    """A new 一般老師 account named `name` in the client's school; returns
    its Teacher's id."""
    username = f"teacher-{next(_usernames)}"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "teacher-pass-123",
            "role": "TEACHER",
            "teacher_name": name,
        },
    )
    assert response.status_code == 201, response.json()
    user_id = response.json()["id"]
    teachers = client.get("/api/v1/teachers/", params={"limit": 1000}).json()
    return next(teacher["id"] for teacher in teachers if teacher["user_id"] == user_id)


def enroll_teacher(
    client: TestClient,
    schedule_version_id: int,
    teacher_id: int,
    *,
    min_weekly_periods: int = 0,
    max_weekly_periods: int = 20,
    unavailable_time_slot_ids: Iterable[int] = (),
) -> None:
    """Adds the teacher to the record's teachers -- or replaces their
    entry -- keeping every other teacher already taking part. The record
    must be 尚未排課 (see mark_status() for later states)."""
    current = client.get(f"/api/v1/schedule-versions/{schedule_version_id}/teachers").json()
    entries = [
        {
            "teacher_id": item["teacher_id"],
            "min_weekly_periods": item["min_weekly_periods"],
            "max_weekly_periods": item["max_weekly_periods"],
            "unavailable_time_slot_ids": item["unavailable_time_slot_ids"],
        }
        for item in current
        if item["teacher_id"] != teacher_id
    ]
    entries.append(
        {
            "teacher_id": teacher_id,
            "min_weekly_periods": min_weekly_periods,
            "max_weekly_periods": max_weekly_periods,
            "unavailable_time_slot_ids": list(unavailable_time_slot_ids),
        }
    )
    response = client.put(
        f"/api/v1/schedule-versions/{schedule_version_id}/teachers", json={"teachers": entries}
    )
    assert response.status_code == 200, response.json()


def create_enrolled_teacher(
    client: TestClient,
    schedule_version_id: int,
    name: str,
    *,
    min_weekly_periods: int = 0,
    max_weekly_periods: int = 20,
) -> int:
    teacher_id = create_teacher(client, name)
    enroll_teacher(
        client,
        schedule_version_id,
        teacher_id,
        min_weekly_periods=min_weekly_periods,
        max_weekly_periods=max_weekly_periods,
    )
    return teacher_id


# --- The school's fixed structure ---
#
# Grades, time slots and class names come from the school's type in the
# app: there is no POST for grades or time slots, and a class name must be
# one of its grade's options. The test school is created bare, so tests
# that build their data through the API add these few rows straight to the
# test database -- the session behind `client` (conftest's get_db
# override).


def db_of(client: TestClient) -> Session:
    override = app.dependency_overrides[get_db]
    session: Session = next(override())
    return session


def create_grade(client: TestClient, name: str = "年級", *, level: int | None = None) -> int:
    """A grade of the test school at `level`, else its lowest unused one."""
    db = db_of(client)
    level = next_free_grade_level(db) if level is None else level
    grade = Grade(school_id=get_test_school_id(db), name=name, level=level)
    db.add(grade)
    db.commit()
    return grade.id


def create_time_slot(
    client: TestClient,
    weekday: int,
    period: int,
    *,
    is_teaching_period: bool = True,
    label: str | None = None,
) -> int:
    """The test school's slot at (weekday, period) -- see time_slot_at()."""
    db = db_of(client)
    slot = time_slot_at(
        db, weekday, period, is_teaching_period=is_teaching_period, label=label
    )
    db.commit()
    return slot.id


def create_class(client: TestClient, grade_id: int, name: str) -> int:
    """A class with a free-text name (the API only takes the grade's
    options; tests not about naming keep their own names)."""
    db = db_of(client)
    class_ = Class(grade_id=grade_id, name=name)
    db.add(class_)
    db.commit()
    return class_.id


# --- v3: 排課紀錄 ---


def create_record(client: TestClient, semester_id: int) -> int:
    """A new 尚未排課 record of the semester -- the owner of the settings a
    test then builds (teachers, grade slots, requirements)."""
    response = client.post("/api/v1/schedule-versions/", json={"semester_id": semester_id})
    assert response.status_code == 201, response.json()
    return int(response.json()["id"])


def mark_status(
    client: TestClient,
    schedule_version_id: int,
    status: str,
    *,
    is_published: bool = False,
    source_status: str = "AUTO",
) -> None:
    """Puts a record straight into a later state, keeping its ids -- for
    tests about what a state allows, not about how it is reached (that is
    run-scheduler / edit / save / publish, tested on their own). EDITING
    also gets the empty record it edits (of `source_status`); COPIED
    copies "from 編號 1"."""
    mark_status_in_db(
        db_of(client),
        schedule_version_id,
        status,
        is_published=is_published,
        source_status=source_status,
    )
