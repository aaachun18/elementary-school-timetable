from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from tests.test_reassign_teacher import Builder

# Task 66: optional filters on the list endpoints --
# GET /schedules?schedule_version_id=, GET /lessons?semester_id=,
# GET /class-subject-requirements?semester_id= -- combined with the existing
# skip/limit and a stable id order. Test data is written straight to the
# database through db_session.

MISSING_ID = 999999


@dataclass
class ListWorld:
    """Two semesters of one academic year, three DRAFT versions:
    - version_a (semester 1): 5 Schedule rows (3 + 2 lessons, 2 requirements)
    - version_b (semester 1): 2 Schedule rows (2 lessons, 1 requirement)
    - version_c (semester 2): 4 Schedule rows (4 lessons, 1 requirement)"""

    semester_1_id: int
    semester_2_id: int
    version_a_id: int
    version_b_id: int
    version_c_id: int


def _build_world(db: Session) -> ListWorld:
    builder = Builder(db)
    semester_2 = builder.semester_in_year(number=2)
    english = builder.subject("英文")
    science = builder.subject("自然")
    math = builder.subject("數學")
    teacher = builder.teacher("老師", [english, science, math])
    c1, c2, c3 = (builder.class_(name) for name in ("一班", "二班", "三班"))

    version_a = builder.version()
    builder.course(version_a, c1, english, teacher, [0, 1, 2])
    builder.course(version_a, c2, science, teacher, [3, 4])
    version_b = builder.version(number=2)
    builder.course(version_b, c3, english, teacher, [0, 1])
    version_c = builder.version(semester=semester_2)
    builder.course(version_c, c1, math, teacher, [0, 1, 2, 3])

    return ListWorld(
        semester_1_id=builder.semester.id,
        semester_2_id=semester_2.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        version_c_id=version_c.id,
    )


def _ids(response: Any) -> list[int]:
    assert response.status_code == 200, response.json()
    return [item["id"] for item in response.json()]


def _schedule_ids(db: Session, version_id: int | None = None) -> list[int]:
    stmt = select(Schedule.id).order_by(Schedule.id)
    if version_id is not None:
        stmt = stmt.where(Schedule.schedule_version_id == version_id)
    return list(db.scalars(stmt).all())


def _lesson_ids(db: Session, semester_id: int | None = None) -> list[int]:
    stmt = select(Lesson.id).order_by(Lesson.id)
    if semester_id is not None:
        stmt = stmt.join(
            ClassSubjectRequirement,
            Lesson.class_subject_requirement_id == ClassSubjectRequirement.id,
        ).where(ClassSubjectRequirement.semester_id == semester_id)
    return list(db.scalars(stmt).all())


def _requirement_ids(db: Session, semester_id: int | None = None) -> list[int]:
    stmt = select(ClassSubjectRequirement.id).order_by(ClassSubjectRequirement.id)
    if semester_id is not None:
        stmt = stmt.where(ClassSubjectRequirement.semester_id == semester_id)
    return list(db.scalars(stmt).all())


def _paged_ids(client: TestClient, url: str, params: dict, page_size: int) -> list[int]:
    """Walks every page of `url` with skip/limit and concatenates the ids."""
    collected: list[int] = []
    skip = 0
    while True:
        page = _ids(client.get(url, params={**params, "skip": skip, "limit": page_size}))
        collected.extend(page)
        if len(page) < page_size:
            return collected
        skip += page_size


def _set_status(db: Session, version_id: int, status: str) -> None:
    version = db.get(ScheduleVersion, version_id)
    assert version is not None
    version.status = status
    db.commit()


# --- GET /schedules?schedule_version_id= ---


def test_list_schedules_filtered_by_version(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)

    for version_id, expected_count in (
        (world.version_a_id, 5),
        (world.version_b_id, 2),
        (world.version_c_id, 4),
    ):
        response = client.get(
            "/api/v1/schedules/", params={"schedule_version_id": version_id}
        )
        assert _ids(response) == _schedule_ids(db_session, version_id)
        assert len(response.json()) == expected_count
        assert {row["schedule_version_id"] for row in response.json()} == {version_id}


def test_list_schedules_filter_with_skip_limit_pages_cleanly(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    params = {"schedule_version_id": world.version_a_id}

    paged = _paged_ids(client, "/api/v1/schedules/", params, page_size=2)

    assert paged == _schedule_ids(db_session, world.version_a_id)
    assert len(paged) == len(set(paged)) == 5


def test_list_schedules_without_filter_returns_every_row(
    client: TestClient, db_session: Session
) -> None:
    _build_world(db_session)

    assert _ids(client.get("/api/v1/schedules/")) == _schedule_ids(db_session)
    assert len(_schedule_ids(db_session)) == 11


def test_list_schedules_missing_version_returns_empty(
    client: TestClient, db_session: Session
) -> None:
    _build_world(db_session)

    response = client.get("/api/v1/schedules/", params={"schedule_version_id": MISSING_ID})

    assert response.status_code == 200
    assert response.json() == []


def test_list_schedules_teacher_filter_sees_published_only(
    teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    _set_status(db_session, world.version_a_id, "PUBLISHED")
    _set_status(db_session, world.version_c_id, "ARCHIVED")
    # version_b stays DRAFT.

    def listed(version_id: int) -> list[int]:
        return _ids(
            teacher_client.get(
                "/api/v1/schedules/", params={"schedule_version_id": version_id}
            )
        )

    assert listed(world.version_a_id) == _schedule_ids(db_session, world.version_a_id)
    # Hidden versions look exactly like missing ones: 200 and [].
    assert listed(world.version_b_id) == []
    assert listed(world.version_c_id) == []
    assert listed(MISSING_ID) == []


# --- GET /lessons?semester_id= ---


def test_list_lessons_filtered_by_semester(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)

    semester_1 = _ids(client.get("/api/v1/lessons/", params={"semester_id": world.semester_1_id}))
    semester_2 = _ids(client.get("/api/v1/lessons/", params={"semester_id": world.semester_2_id}))

    assert semester_1 == _lesson_ids(db_session, world.semester_1_id)
    assert len(semester_1) == 7
    assert semester_2 == _lesson_ids(db_session, world.semester_2_id)
    assert len(semester_2) == 4
    assert set(semester_1).isdisjoint(semester_2)


def test_list_lessons_filter_with_skip_limit_pages_cleanly(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)

    paged = _paged_ids(
        client, "/api/v1/lessons/", {"semester_id": world.semester_1_id}, page_size=3
    )

    assert paged == _lesson_ids(db_session, world.semester_1_id)
    assert len(paged) == len(set(paged)) == 7


def test_list_lessons_without_filter_and_missing_semester(
    client: TestClient, db_session: Session
) -> None:
    _build_world(db_session)

    assert _ids(client.get("/api/v1/lessons/")) == _lesson_ids(db_session)
    assert _ids(client.get("/api/v1/lessons/", params={"semester_id": MISSING_ID})) == []


# --- GET /class-subject-requirements?semester_id= ---


def test_list_requirements_filtered_by_semester(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    url = "/api/v1/class-subject-requirements/"

    semester_1 = client.get(url, params={"semester_id": world.semester_1_id})
    semester_2 = client.get(url, params={"semester_id": world.semester_2_id})

    assert _ids(semester_1) == _requirement_ids(db_session, world.semester_1_id)
    assert len(semester_1.json()) == 3
    assert {row["semester_id"] for row in semester_1.json()} == {world.semester_1_id}
    assert _ids(semester_2) == _requirement_ids(db_session, world.semester_2_id)
    assert len(semester_2.json()) == 1


def test_list_requirements_filter_with_skip_limit_pages_cleanly(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)

    paged = _paged_ids(
        client,
        "/api/v1/class-subject-requirements/",
        {"semester_id": world.semester_1_id},
        page_size=2,
    )

    assert paged == _requirement_ids(db_session, world.semester_1_id)
    assert len(paged) == len(set(paged)) == 3


def test_list_requirements_without_filter_and_missing_semester(
    client: TestClient, db_session: Session
) -> None:
    _build_world(db_session)
    url = "/api/v1/class-subject-requirements/"

    assert _ids(client.get(url)) == _requirement_ids(db_session)
    assert _ids(client.get(url, params={"semester_id": MISSING_ID})) == []


# --- Shared: validation and authentication ---


@pytest.mark.parametrize(
    ("url", "param"),
    [
        ("/api/v1/schedules/", "schedule_version_id"),
        ("/api/v1/lessons/", "semester_id"),
        ("/api/v1/class-subject-requirements/", "semester_id"),
    ],
)
def test_list_filter_rejects_non_integer(client: TestClient, url: str, param: str) -> None:
    assert client.get(url, params={param: "abc"}).status_code == 422


@pytest.mark.parametrize(
    ("url", "param"),
    [
        ("/api/v1/schedules/", "schedule_version_id"),
        ("/api/v1/lessons/", "semester_id"),
        ("/api/v1/class-subject-requirements/", "semester_id"),
    ],
)
def test_list_filter_unauthenticated_returns_401(
    unauthenticated_client: TestClient, url: str, param: str
) -> None:
    assert unauthenticated_client.get(url, params={param: 1}).status_code == 401
