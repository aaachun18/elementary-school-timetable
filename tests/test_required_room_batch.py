from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import mark_status_in_db
from tests.test_lesson_pattern_batch import URL, _two_classes
from tests.test_schedule import _create_room

# PATCH /class-subject-requirements/required-rooms -- the wizard's
# 「複製此教室設定至所有同年級班級」. Every item is checked like a single
# PATCH; all of them are saved in one transaction, or none.


def _room(client: TestClient, requirement_id: int) -> Any:
    return client.get(f"{URL}/{requirement_id}").json()["required_room_id"]


def test_saves_every_item(client: TestClient) -> None:
    _, first, second = _two_classes(client, 10401)
    room_id = _create_room(client, "自然教室 10401")

    response = client.patch(
        f"{URL}/required-rooms",
        json={"items": [{"id": first, "required_room_id": room_id}, {"id": second, "required_room_id": room_id}]},
    )

    assert response.status_code == 200, response.json()
    assert [row["required_room_id"] for row in response.json()] == [room_id, room_id]
    assert _room(client, first) == _room(client, second) == room_id


def test_none_means_the_class_own_room(client: TestClient) -> None:
    _, first, _ = _two_classes(client, 10402)
    room_id = _create_room(client, "自然教室 10402")
    client.patch(f"{URL}/{first}", json={"required_room_id": room_id})

    response = client.patch(f"{URL}/required-rooms", json={"items": [{"id": first, "required_room_id": None}]})

    assert response.status_code == 200
    assert _room(client, first) is None


def test_an_unknown_requirement_saves_nothing(client: TestClient) -> None:
    _, first, _ = _two_classes(client, 10403)
    room_id = _create_room(client, "自然教室 10403")

    response = client.patch(
        f"{URL}/required-rooms",
        json={"items": [{"id": first, "required_room_id": room_id}, {"id": 999999, "required_room_id": room_id}]},
    )

    assert response.status_code == 404
    assert _room(client, first) is None


def test_an_unknown_room_saves_nothing(client: TestClient) -> None:
    _, first, second = _two_classes(client, 10404)
    room_id = _create_room(client, "自然教室 10404")

    response = client.patch(
        f"{URL}/required-rooms",
        json={"items": [{"id": first, "required_room_id": room_id}, {"id": second, "required_room_id": 999999}]},
    )

    assert response.status_code == 422
    assert _room(client, first) is None
    assert _room(client, second) is None


def test_a_scheduled_record_is_locked(client: TestClient, db_session: Session) -> None:
    record_id, first, _ = _two_classes(client, 10405)
    room_id = _create_room(client, "自然教室 10405")
    mark_status_in_db(db_session, record_id, "AUTO")

    response = client.patch(f"{URL}/required-rooms", json={"items": [{"id": first, "required_room_id": room_id}]})

    assert response.status_code == 409
    assert _room(client, first) is None


def test_a_teacher_cannot_change_rooms(teacher_client: TestClient, client: TestClient) -> None:
    _, first, _ = _two_classes(client, 10406)

    response = teacher_client.patch(f"{URL}/required-rooms", json={"items": [{"id": first, "required_room_id": None}]})

    assert response.status_code == 403
