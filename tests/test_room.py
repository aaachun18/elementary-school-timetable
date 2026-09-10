from fastapi.testclient import TestClient


def test_create_room(client: TestClient) -> None:
    response = client.post(
        "/api/v1/rooms/",
        json={"name": "101教室", "room_type": "普通教室", "capacity": 30},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "101教室"
    assert data["room_type"] == "普通教室"
    assert data["capacity"] == 30
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_room_without_capacity(client: TestClient) -> None:
    response = client.post(
        "/api/v1/rooms/",
        json={"name": "No Capacity Room", "room_type": "普通教室"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["capacity"] is None


def test_create_room_cannot_set_is_active(client: TestClient) -> None:
    response = client.post(
        "/api/v1/rooms/",
        json={
            "name": "101教室",
            "room_type": "普通教室",
            "capacity": 30,
            "is_active": False,
        },
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_get_room_list(client: TestClient) -> None:
    client.post(
        "/api/v1/rooms/",
        json={"name": "List Room", "room_type": "普通教室", "capacity": 20},
    )

    response = client.get("/api/v1/rooms/")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "List Room" in names


def test_get_room_by_id(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/rooms/",
        json={"name": "Get Room", "room_type": "普通教室", "capacity": 20},
    )
    room_id = create_response.json()["id"]

    response = client.get(f"/api/v1/rooms/{room_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Get Room"


def test_get_room_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/rooms/999999")

    assert response.status_code == 404


def test_update_room(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/rooms/",
        json={"name": "Old Room", "room_type": "普通教室", "capacity": 20},
    )
    room_id = create_response.json()["id"]

    response = client.patch(f"/api/v1/rooms/{room_id}", json={"capacity": 35})

    assert response.status_code == 200
    assert response.json()["capacity"] == 35


def test_update_room_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/rooms/999999", json={"capacity": 10})

    assert response.status_code == 404


def test_delete_room(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/rooms/",
        json={"name": "Delete Room", "room_type": "普通教室", "capacity": 20},
    )
    room_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/rooms/{room_id}")

    assert response.status_code == 204


def test_delete_room_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/rooms/999999")

    assert response.status_code == 404
