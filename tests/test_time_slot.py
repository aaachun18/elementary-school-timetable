from fastapi.testclient import TestClient

from tests.api_helpers import create_time_slot

# A school's time slot grid is built with the school (test_school.py) and
# fixed: no POST or DELETE, only label and is_teaching_period change.


def test_get_time_slot_list_ordered_by_weekday_and_period(client: TestClient) -> None:
    later = create_time_slot(client, 2, 1)
    earlier = create_time_slot(client, 1, 3)
    earliest = create_time_slot(client, 1, 0, is_teaching_period=False, label="早自習")

    response = client.get("/api/v1/time-slots/")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [earliest, earlier, later]
    assert data[0]["label"] == "早自習"
    assert data[0]["is_teaching_period"] is False
    assert "start_time" not in data[0]
    assert "end_time" not in data[0]


def test_get_time_slot_by_id(client: TestClient) -> None:
    time_slot_id = create_time_slot(client, 1, 3)

    response = client.get(f"/api/v1/time-slots/{time_slot_id}")

    assert response.status_code == 200
    assert response.json()["period"] == 3


def test_get_time_slot_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/time-slots/999999")

    assert response.status_code == 404


def test_time_slots_cannot_be_created_or_deleted(client: TestClient) -> None:
    time_slot_id = create_time_slot(client, 1, 1)

    response = client.post("/api/v1/time-slots/", json={"weekday": 1, "period": 2})
    assert response.status_code == 405
    assert client.delete(f"/api/v1/time-slots/{time_slot_id}").status_code == 405


def test_update_time_slot_label_and_teaching(client: TestClient) -> None:
    time_slot_id = create_time_slot(client, 1, 4)

    response = client.patch(
        f"/api/v1/time-slots/{time_slot_id}",
        json={"label": "導師時間", "is_teaching_period": False},
    )

    assert response.status_code == 200
    assert response.json()["label"] == "導師時間"
    assert response.json()["is_teaching_period"] is False


def test_update_time_slot_ignores_weekday_and_period(client: TestClient) -> None:
    """The grid position is fixed: only label / is_teaching_period are
    taken, anything else in the body is dropped."""
    time_slot_id = create_time_slot(client, 1, 4)

    response = client.patch(
        f"/api/v1/time-slots/{time_slot_id}", json={"weekday": 3, "period": 9}
    )

    assert response.status_code == 200
    assert (response.json()["weekday"], response.json()["period"]) == (1, 4)


def test_update_time_slot_blank_label_becomes_null(client: TestClient) -> None:
    time_slot_id = create_time_slot(client, 1, 0, is_teaching_period=False, label="早自習")

    response = client.patch(f"/api/v1/time-slots/{time_slot_id}", json={"label": "   "})

    assert response.status_code == 200
    assert response.json()["label"] is None


def test_update_time_slot_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/time-slots/999999", json={"label": "x"})

    assert response.status_code == 404


def test_bulk_update_time_slots_changes_every_listed_slot(client: TestClient) -> None:
    first = create_time_slot(client, 1, 1)
    second = create_time_slot(client, 2, 1)
    untouched = create_time_slot(client, 3, 1)

    response = client.patch(
        "/api/v1/time-slots/",
        json={
            "time_slots": [
                {"id": first, "label": "晨光時間", "is_teaching_period": False},
                {"id": second, "label": "第一節"},
            ]
        },
    )

    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()}
    assert by_id[first]["label"] == "晨光時間"
    assert by_id[first]["is_teaching_period"] is False
    assert by_id[second]["label"] == "第一節"
    assert by_id[second]["is_teaching_period"] is True
    assert by_id[untouched]["label"] is None


def test_bulk_update_time_slots_is_all_or_nothing(client: TestClient) -> None:
    time_slot_id = create_time_slot(client, 1, 1)

    response = client.patch(
        "/api/v1/time-slots/",
        json={
            "time_slots": [
                {"id": time_slot_id, "label": "改了"},
                {"id": 999999, "label": "不存在"},
            ]
        },
    )

    assert response.status_code == 422
    assert client.get(f"/api/v1/time-slots/{time_slot_id}").json()["label"] is None


def test_teacher_cannot_update_time_slots(
    client: TestClient, teacher_client: TestClient
) -> None:
    time_slot_id = create_time_slot(client, 1, 1)

    assert teacher_client.patch(
        f"/api/v1/time-slots/{time_slot_id}", json={"label": "x"}
    ).status_code == 403
    assert teacher_client.patch(
        "/api/v1/time-slots/", json={"time_slots": [{"id": time_slot_id, "label": "x"}]}
    ).status_code == 403
