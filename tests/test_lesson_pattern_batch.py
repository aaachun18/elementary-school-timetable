from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.lesson_pattern import TOTAL_MESSAGE
from tests.conftest import mark_status_in_db
from tests.test_scheduler import _create_class, _create_record, _create_subject

# Task 103: PATCH /class-subject-requirements/lesson-patterns -- the wizard's
# 「複製此連堂設定至所有同年級班級」. Every item is checked like a single
# PATCH; all of them are saved in one transaction, or none.

URL = "/api/v1/class-subject-requirements"


def _requirement(client: TestClient, record_id: int, class_id: int, subject_id: int, weekly_periods: int) -> int:
    response = client.post(
        f"{URL}/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": weekly_periods,
        },
    )
    assert response.status_code == 201, response.json()
    requirement_id: int = response.json()["id"]
    return requirement_id


def _pattern(client: TestClient, requirement_id: int) -> Any:
    return client.get(f"{URL}/{requirement_id}").json()["lesson_pattern"]


def _two_classes(client: TestClient, year: int) -> tuple[int, int, int]:
    """A record with two classes taking the same 3-period subject."""
    record_id = _create_record(client, year)
    subject_id = _create_subject(client, name=f"Subject {year}")
    first = _requirement(client, record_id, _create_class(client, level=1), subject_id, 3)
    second = _requirement(client, record_id, _create_class(client, level=2), subject_id, 3)
    return record_id, first, second


def test_saves_every_item_and_normalizes_the_pattern(client: TestClient) -> None:
    _, first, second = _two_classes(client, 10301)

    response = client.patch(
        f"{URL}/lesson-patterns",
        json={"items": [{"id": first, "lesson_pattern": "1+2"}, {"id": second, "lesson_pattern": "2+1"}]},
    )

    assert response.status_code == 200, response.json()
    assert [row["lesson_pattern"] for row in response.json()] == ["2+1", "2+1"]
    assert _pattern(client, first) == _pattern(client, second) == "2+1"


def test_regroups_existing_lessons_like_a_single_patch(client: TestClient) -> None:
    record_id, first, _ = _two_classes(client, 10302)
    client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    client.patch(f"{URL}/lesson-patterns", json={"items": [{"id": first, "lesson_pattern": "2+1"}]})

    rows = client.get("/api/v1/lessons/", params={"schedule_version_id": record_id}).json()
    blocks = sorted(
        (row["sequence_number"], row["block_no"], row["block_seq"])
        for row in rows
        if row["class_subject_requirement_id"] == first
    )
    assert blocks == [(1, 1, 1), (2, 1, 2), (3, 2, 1)]


def test_one_pattern_that_does_not_add_up_saves_nothing(client: TestClient) -> None:
    record_id = _create_record(client, 10303)
    subject_id = _create_subject(client, name="Subject 10303")
    three = _requirement(client, record_id, _create_class(client, level=1), subject_id, 3)
    four = _requirement(client, record_id, _create_class(client, level=2), subject_id, 4)

    response = client.patch(
        f"{URL}/lesson-patterns",
        json={"items": [{"id": three, "lesson_pattern": "2+1"}, {"id": four, "lesson_pattern": "2+1"}]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == TOTAL_MESSAGE
    assert _pattern(client, three) is None
    assert _pattern(client, four) is None


def test_an_unknown_requirement_saves_nothing(client: TestClient) -> None:
    _, first, _ = _two_classes(client, 10304)

    response = client.patch(
        f"{URL}/lesson-patterns",
        json={"items": [{"id": first, "lesson_pattern": "2+1"}, {"id": 999999, "lesson_pattern": "2+1"}]},
    )

    assert response.status_code == 404
    assert _pattern(client, first) is None


def test_a_scheduled_record_is_locked(client: TestClient, db_session: Session) -> None:
    record_id, first, second = _two_classes(client, 10305)
    mark_status_in_db(db_session, record_id, "AUTO")

    response = client.patch(
        f"{URL}/lesson-patterns",
        json={"items": [{"id": first, "lesson_pattern": "2+1"}, {"id": second, "lesson_pattern": "2+1"}]},
    )

    assert response.status_code == 409
    assert _pattern(client, first) is None
    assert _pattern(client, second) is None


def test_needs_at_least_one_item(client: TestClient) -> None:
    assert client.patch(f"{URL}/lesson-patterns", json={"items": []}).status_code == 422


def test_a_teacher_cannot_change_patterns(teacher_client: TestClient, client: TestClient) -> None:
    _, first, _ = _two_classes(client, 10306)

    response = teacher_client.patch(
        f"{URL}/lesson-patterns", json={"items": [{"id": first, "lesson_pattern": "2+1"}]}
    )

    assert response.status_code == 403
    assert _pattern(client, first) is None
