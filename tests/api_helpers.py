"""Task 98: shared test helpers for the two ways a teacher reaches a
schedule now -- an 一般老師 account (which creates its Teacher), and taking
part in a semester (SemesterTeacher, with that semester's weekly periods
range and unavailable slots). `client` is the test school's 教學組長."""

from collections.abc import Iterable
from itertools import count

from fastapi.testclient import TestClient

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
    semester_id: int,
    teacher_id: int,
    *,
    min_weekly_periods: int = 0,
    max_weekly_periods: int = 20,
    unavailable_time_slot_ids: Iterable[int] = (),
) -> None:
    """Adds the teacher to the semester's teachers -- or replaces their
    entry -- keeping every other teacher already taking part."""
    current = client.get(f"/api/v1/semesters/{semester_id}/teachers").json()
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
    response = client.put(f"/api/v1/semesters/{semester_id}/teachers", json={"teachers": entries})
    assert response.status_code == 200, response.json()


def create_enrolled_teacher(
    client: TestClient,
    semester_id: int,
    name: str,
    *,
    min_weekly_periods: int = 0,
    max_weekly_periods: int = 20,
) -> int:
    teacher_id = create_teacher(client, name)
    enroll_teacher(
        client,
        semester_id,
        teacher_id,
        min_weekly_periods=min_weekly_periods,
        max_weekly_periods=max_weekly_periods,
    )
    return teacher_id
