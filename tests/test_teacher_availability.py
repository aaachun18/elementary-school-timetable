from fastapi.testclient import TestClient


def _create_teacher(client: TestClient, name: str = "Teacher A") -> int:
    response = client.post(
        "/api/v1/teachers/",
        json={"name": name, "min_weekly_periods": 10, "max_weekly_periods": 20},
    )
    teacher_id: int = response.json()["id"]
    return teacher_id


def _create_time_slot(client: TestClient, period: int = 1) -> int:
    response = client.post(
        "/api/v1/time-slots/",
        json={
            "weekday": 1,
            "period": period,
            "start_time": "08:00:00",
            "end_time": "08:40:00",
            "is_teaching_period": True,
        },
    )
    time_slot_id: int = response.json()["id"]
    return time_slot_id


def test_add_teacher_unavailable_slot(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    time_slot_id = _create_time_slot(client)

    response = client.post(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots",
        json={"time_slot_id": time_slot_id},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == time_slot_id
    assert data["period"] == 1


def test_list_teacher_unavailable_slots(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    time_slot_id = _create_time_slot(client)
    client.post(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots",
        json={"time_slot_id": time_slot_id},
    )

    response = client.get(f"/api/v1/teachers/{teacher_id}/unavailable-slots")

    assert response.status_code == 200
    time_slot_ids = [item["id"] for item in response.json()]
    assert time_slot_id in time_slot_ids


def test_add_teacher_unavailable_slot_duplicate_conflict(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    time_slot_id = _create_time_slot(client)
    client.post(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots",
        json={"time_slot_id": time_slot_id},
    )

    response = client.post(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots",
        json={"time_slot_id": time_slot_id},
    )

    assert response.status_code == 409


def test_add_teacher_unavailable_slot_invalid_teacher_id(client: TestClient) -> None:
    time_slot_id = _create_time_slot(client)

    response = client.post(
        "/api/v1/teachers/999999/unavailable-slots",
        json={"time_slot_id": time_slot_id},
    )

    assert response.status_code == 422


def test_add_teacher_unavailable_slot_invalid_time_slot_id(
    client: TestClient,
) -> None:
    teacher_id = _create_teacher(client)

    response = client.post(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots",
        json={"time_slot_id": 999999},
    )

    assert response.status_code == 422


def test_list_teacher_unavailable_slots_teacher_not_found(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/teachers/999999/unavailable-slots")

    assert response.status_code == 404


def test_remove_teacher_unavailable_slot(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    time_slot_id = _create_time_slot(client)
    client.post(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots",
        json={"time_slot_id": time_slot_id},
    )

    response = client.delete(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots/{time_slot_id}"
    )

    assert response.status_code == 204


def test_remove_teacher_unavailable_slot_not_found(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    time_slot_id = _create_time_slot(client)
    client.post(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots",
        json={"time_slot_id": time_slot_id},
    )
    client.delete(f"/api/v1/teachers/{teacher_id}/unavailable-slots/{time_slot_id}")

    response = client.delete(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots/{time_slot_id}"
    )

    assert response.status_code == 404
