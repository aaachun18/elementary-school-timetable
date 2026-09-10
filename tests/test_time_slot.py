from fastapi.testclient import TestClient


def _time_slot_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "weekday": 1,
        "period": 1,
        "start_time": "08:00:00",
        "end_time": "08:40:00",
        "is_teaching_period": True,
    }
    payload.update(overrides)
    return payload


def test_create_time_slot(client: TestClient) -> None:
    response = client.post("/api/v1/time-slots/", json=_time_slot_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["weekday"] == 1
    assert data["period"] == 1
    assert data["start_time"] == "08:00:00"
    assert data["end_time"] == "08:40:00"
    assert data["is_teaching_period"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_time_slot_without_start_end_time(client: TestClient) -> None:
    response = client.post(
        "/api/v1/time-slots/",
        json={"weekday": 1, "period": 1, "is_teaching_period": True},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["start_time"] is None
    assert data["end_time"] is None


def test_create_time_slot_can_set_is_teaching_period(client: TestClient) -> None:
    # Unlike is_active elsewhere, is_teaching_period is a structural
    # attribute decided at creation time (Task 9 design decision), so
    # TimeSlotCreate is expected to honor it rather than force it to True.
    response = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(is_teaching_period=False)
    )

    assert response.status_code == 201
    assert response.json()["is_teaching_period"] is False


def test_get_time_slot_list(client: TestClient) -> None:
    client.post("/api/v1/time-slots/", json=_time_slot_payload(period=2))

    response = client.get("/api/v1/time-slots/")

    assert response.status_code == 200
    periods = [item["period"] for item in response.json()]
    assert 2 in periods


def test_get_time_slot_by_id(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=3)
    )
    time_slot_id = create_response.json()["id"]

    response = client.get(f"/api/v1/time-slots/{time_slot_id}")

    assert response.status_code == 200
    assert response.json()["period"] == 3


def test_get_time_slot_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/time-slots/999999")

    assert response.status_code == 404


def test_update_time_slot(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=4)
    )
    time_slot_id = create_response.json()["id"]

    response = client.patch(f"/api/v1/time-slots/{time_slot_id}", json={"period": 5})

    assert response.status_code == 200
    assert response.json()["period"] == 5


def test_update_time_slot_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/time-slots/999999", json={"period": 1})

    assert response.status_code == 404


def test_delete_time_slot(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=6)
    )
    time_slot_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/time-slots/{time_slot_id}")

    assert response.status_code == 204


def test_delete_time_slot_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/time-slots/999999")

    assert response.status_code == 404


def test_create_time_slot_weekday_check_violation(client: TestClient) -> None:
    response = client.post("/api/v1/time-slots/", json=_time_slot_payload(weekday=9))

    assert response.status_code == 409
