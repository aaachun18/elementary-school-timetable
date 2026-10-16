import re
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import Lesson
from app.services.lesson_pattern import (
    BLOCK_SIZE_MESSAGE,
    FORMAT_MESSAGE,
    TOTAL_MESSAGE,
    assign_block_fields,
    block_positions,
    check_pattern_total,
    normalize_lesson_pattern,
)
from tests.test_requirement_edit_lock import _build_world, _set_status
from tests.test_scheduler import (
    _add_teacher_subject,
    _create_class,
    _create_schedule_version,
    _create_semester,
    _create_subject,
    _create_teacher,
    _create_time_slot,
)

# Task 87: ClassSubjectRequirement.lesson_pattern (連堂樣式, e.g. "2+1") and
# Lesson.block_no / block_seq -- validation, the edit lock, generate-lessons
# and run-scheduler end to end.

URL = "/api/v1/class-subject-requirements"
LOCKED_MESSAGE = "此排課需求已被已發布或已封存的課表使用，無法修改"


# --- Pure helpers ---


@pytest.mark.parametrize(
    ("given", "stored"),
    [("2+1", "2+1"), ("1+2", "2+1"), (" 2 + 2 + 1 ", "2+2+1"), ("1+2+2", "2+2+1"), ("3", "3"), (None, None), ("", None), ("   ", None)],
)
def test_normalize_sorts_blocks_largest_first(given: str | None, stored: str | None) -> None:
    assert normalize_lesson_pattern(given) == stored


@pytest.mark.parametrize("bad", ["2+", "+1", "a", "2,1", "2++1", "2-1", "1.5"])
def test_normalize_rejects_bad_format(bad: str) -> None:
    with pytest.raises(ValueError, match=re.escape(FORMAT_MESSAGE)):
        normalize_lesson_pattern(bad)


@pytest.mark.parametrize("bad", ["4", "0+2", "2+4", "10"])
def test_normalize_rejects_blocks_outside_1_to_3(bad: str) -> None:
    with pytest.raises(ValueError, match=re.escape(BLOCK_SIZE_MESSAGE)):
        normalize_lesson_pattern(bad)


def test_check_pattern_total() -> None:
    check_pattern_total("2+1", 3)
    check_pattern_total(None, 7)
    with pytest.raises(ValueError, match=re.escape(TOTAL_MESSAGE)):
        check_pattern_total("2+1", 4)


def test_block_positions_fill_blocks_in_order() -> None:
    assert block_positions("2+2+1", 5) == [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1)]
    assert block_positions("2+1", 2) == [(1, 1), (1, 2)]  # fewer lessons than the pattern
    assert block_positions("2+1", 4) == [(1, 1), (1, 2), (2, 1), (None, None)]  # more
    assert block_positions(None, 2) == [(None, None), (None, None)]


@dataclass
class _FakeLesson:
    sequence_number: int
    block_no: int | None = None
    block_seq: int | None = None


def test_assign_block_fields_follows_sequence_number_and_reports_changes() -> None:
    lessons = [_FakeLesson(3), _FakeLesson(1), _FakeLesson(2)]

    assert assign_block_fields(lessons, "2+1") is True  # type: ignore[arg-type]
    assert [(lesson.sequence_number, lesson.block_no, lesson.block_seq) for lesson in lessons] == [
        (3, 2, 1),
        (1, 1, 1),
        (2, 1, 2),
    ]
    assert assign_block_fields(lessons, "2+1") is False  # type: ignore[arg-type]
    assert assign_block_fields(lessons, None) is True  # type: ignore[arg-type]
    assert all(lesson.block_no is None and lesson.block_seq is None for lesson in lessons)


# --- API: create / read / update ---


@dataclass
class Setup:
    semester_id: int
    class_id: int
    subject_id: int
    teacher_id: int


def _setup(client: TestClient, year: int) -> Setup:
    semester_id = _create_semester(client, year)
    class_id = _create_class(client, level=year)
    subject_id = _create_subject(client, name=f"Subject {year}")
    teacher_id = _create_teacher(client, name=f"Teacher {year}")
    _add_teacher_subject(client, teacher_id, subject_id)
    return Setup(semester_id, class_id, subject_id, teacher_id)


def _create(client: TestClient, setup: Setup, weekly_periods: int, pattern: str | None) -> Any:
    body: dict[str, Any] = {
        "semester_id": setup.semester_id,
        "class_id": setup.class_id,
        "subject_id": setup.subject_id,
        "weekly_periods": weekly_periods,
    }
    if pattern is not None:
        body["lesson_pattern"] = pattern
    return client.post(f"{URL}/", json=body)


def _messages(response: Any) -> str:
    detail = response.json()["detail"]
    return detail if isinstance(detail, str) else " ".join(error["msg"] for error in detail)


def test_create_stores_the_normalized_pattern_and_reads_it_back(client: TestClient) -> None:
    setup = _setup(client, 8701)

    created = _create(client, setup, 3, "1+2")

    assert created.status_code == 201, created.json()
    assert created.json()["lesson_pattern"] == "2+1"
    single = client.get(f"{URL}/{created.json()['id']}").json()
    listed = next(row for row in client.get(f"{URL}/").json() if row["id"] == created.json()["id"])
    assert single["lesson_pattern"] == listed["lesson_pattern"] == "2+1"


def test_create_without_pattern_keeps_it_empty(client: TestClient) -> None:
    setup = _setup(client, 8702)

    assert _create(client, setup, 3, None).json()["lesson_pattern"] is None


@pytest.mark.parametrize(
    ("weekly_periods", "pattern", "message"),
    [
        (3, "2+", FORMAT_MESSAGE),
        (3, "a", FORMAT_MESSAGE),
        (4, "4", BLOCK_SIZE_MESSAGE),
        (3, "0+3", BLOCK_SIZE_MESSAGE),
        (4, "2+1", TOTAL_MESSAGE),
        (2, "2+1", TOTAL_MESSAGE),
    ],
)
def test_create_rejects_bad_patterns_with_422(
    client: TestClient, weekly_periods: int, pattern: str, message: str
) -> None:
    setup = _setup(client, 8703)

    response = _create(client, setup, weekly_periods, pattern)

    assert response.status_code == 422
    assert message in _messages(response)


def test_update_keeps_weekly_periods_and_pattern_consistent(client: TestClient) -> None:
    setup = _setup(client, 8704)
    requirement_id = _create(client, setup, 3, "2+1").json()["id"]

    only_periods = client.patch(f"{URL}/{requirement_id}", json={"weekly_periods": 4})
    both = client.patch(f"{URL}/{requirement_id}", json={"weekly_periods": 4, "lesson_pattern": "1+1+2"})
    bad_format = client.patch(f"{URL}/{requirement_id}", json={"lesson_pattern": "2x2"})
    cleared = client.patch(f"{URL}/{requirement_id}", json={"lesson_pattern": None})

    assert only_periods.status_code == 422
    assert only_periods.json()["detail"] == TOTAL_MESSAGE
    assert both.status_code == 200, both.json()
    assert both.json()["lesson_pattern"] == "2+1+1"
    assert bad_format.status_code == 422
    assert FORMAT_MESSAGE in _messages(bad_format)
    assert cleared.status_code == 200
    assert cleared.json()["lesson_pattern"] is None


def test_pattern_is_a_locked_field(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)  # 2 lessons placed in a version
    _set_status(db_session, world.version, "PUBLISHED")

    changed = client.patch(f"{URL}/{world.requirement.id}", json={"lesson_pattern": "2"})
    same = client.patch(f"{URL}/{world.requirement.id}", json={"lesson_pattern": None})

    assert changed.status_code == 409
    assert changed.json()["detail"] == LOCKED_MESSAGE
    assert same.status_code == 200  # sending the current value is not a change


# --- generate-lessons and Lesson fields ---


def _lessons(client: TestClient, setup: Setup) -> list[tuple[int, int | None, int | None]]:
    rows = client.get("/api/v1/lessons/", params={"semester_id": setup.semester_id}).json()
    return sorted((row["sequence_number"], row["block_no"], row["block_seq"]) for row in rows)


def test_generate_lessons_fills_block_fields_from_the_pattern(client: TestClient) -> None:
    setup = _setup(client, 8705)
    _create(client, setup, 5, "2+2+1")
    version_id = _create_schedule_version(client, setup.semester_id)

    response = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    assert response.status_code == 200
    assert _lessons(client, setup) == [(1, 1, 1), (2, 1, 2), (3, 2, 1), (4, 2, 2), (5, 3, 1)]


def test_generate_lessons_without_pattern_leaves_block_fields_empty(client: TestClient) -> None:
    setup = _setup(client, 8706)
    _create(client, setup, 3, None)
    version_id = _create_schedule_version(client, setup.semester_id)

    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    assert _lessons(client, setup) == [(1, None, None), (2, None, None), (3, None, None)]


def test_changing_the_pattern_regroups_existing_lessons(client: TestClient) -> None:
    setup = _setup(client, 8707)
    requirement_id = _create(client, setup, 5, "2+2+1").json()["id"]
    version_id = _create_schedule_version(client, setup.semester_id)
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    client.patch(f"{URL}/{requirement_id}", json={"lesson_pattern": "3+2"})
    regrouped = _lessons(client, setup)
    client.patch(f"{URL}/{requirement_id}", json={"lesson_pattern": None})

    assert regrouped == [(1, 1, 1), (2, 1, 2), (3, 1, 3), (4, 2, 1), (5, 2, 2)]
    assert _lessons(client, setup) == [(n, None, None) for n in range(1, 6)]


def test_generate_lessons_brings_stale_block_fields_back_in_line(
    client: TestClient, db_session: Session
) -> None:
    setup = _setup(client, 8708)
    _create(client, setup, 3, "2+1")
    version_id = _create_schedule_version(client, setup.semester_id)
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")
    for lesson in db_session.scalars(select(Lesson)).all():
        lesson.block_no = None
        lesson.block_seq = None
    db_session.commit()

    again = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    assert again.json()["created_count"] == 0
    assert _lessons(client, setup) == [(1, 1, 1), (2, 1, 2), (3, 2, 1)]


# --- run-scheduler end to end ---


def _slot_positions(client: TestClient) -> dict[int, tuple[int, int]]:
    return {row["id"]: (row["weekday"], row["period"]) for row in client.get("/api/v1/time-slots/").json()}


def test_run_scheduler_places_a_double_period_and_a_single_on_another_day(client: TestClient) -> None:
    setup = _setup(client, 8709)
    for weekday in (1, 2):
        for period in (1, 2, 3):
            _create_time_slot(client, weekday=weekday, period=period)
    _create(client, setup, 3, "2+1")
    version_id = _create_schedule_version(client, setup.semester_id)
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 200, response.json()
    positions = _slot_positions(client)
    lessons = {row["id"]: row for row in client.get("/api/v1/lessons/", params={"semester_id": setup.semester_id}).json()}
    rows = client.get("/api/v1/schedules/", params={"schedule_version_id": version_id}).json()
    by_block: dict[int, list[tuple[int, tuple[int, int], int]]] = {}
    for row in rows:
        lesson = lessons[row["lesson_id"]]
        by_block.setdefault(lesson["block_no"], []).append(
            (lesson["block_seq"], positions[row["time_slot_id"]], row["teacher_id"])
        )
    double = sorted(by_block[1])
    single = by_block[2]
    assert double[0][1][0] == double[1][1][0]  # same day
    assert double[1][1][1] == double[0][1][1] + 1  # adjacent periods, in order
    assert double[0][2] == double[1][2]  # same teacher
    assert single[0][1][0] != double[0][1][0]  # different day


def test_run_scheduler_reports_a_block_too_long_before_searching(client: TestClient) -> None:
    setup = _setup(client, 8710)
    for weekday in (1, 2, 3):
        for period in (1, 2):
            _create_time_slot(client, weekday=weekday, period=period)
    requirement_id = _create(client, setup, 3, "3").json()["id"]
    version_id = _create_schedule_version(client, setup.semester_id)
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    violation = next(v for v in data["post_hoc_violations"] if v["type"] == "STATIC_BLOCK_TOO_LONG")
    assert violation["class_subject_requirement_id"] == requirement_id
    assert violation["class_id"] == setup.class_id
    assert violation["subject_id"] == setup.subject_id
    assert client.get("/api/v1/schedules/", params={"schedule_version_id": version_id}).json() == []
