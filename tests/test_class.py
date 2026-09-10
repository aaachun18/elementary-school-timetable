from fastapi.testclient import TestClient


def _create_grade(client: TestClient, level: int) -> int:
    response = client.post(
        "/api/v1/grades/", json={"name": f"Grade {level}", "level": level}
    )
    grade_id: int = response.json()["id"]
    return grade_id


def test_create_class(client: TestClient) -> None:
    grade_id = _create_grade(client, level=1)

    response = client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": "一年一班"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["grade_id"] == grade_id
    assert data["name"] == "一年一班"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_class_cannot_set_is_active(client: TestClient) -> None:
    grade_id = _create_grade(client, level=2)

    response = client.post(
        "/api/v1/classes/",
        json={"grade_id": grade_id, "name": "二年一班", "is_active": False},
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_get_class_list(client: TestClient) -> None:
    grade_id = _create_grade(client, level=3)
    client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": "List Class"}
    )

    response = client.get("/api/v1/classes/")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "List Class" in names


def test_get_class_by_id(client: TestClient) -> None:
    grade_id = _create_grade(client, level=4)
    create_response = client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": "Get Class"}
    )
    class_id = create_response.json()["id"]

    response = client.get(f"/api/v1/classes/{class_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Get Class"


def test_get_class_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/classes/999999")

    assert response.status_code == 404


def test_update_class(client: TestClient) -> None:
    grade_id = _create_grade(client, level=5)
    create_response = client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": "Old Class"}
    )
    class_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/classes/{class_id}", json={"name": "New Class"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Class"


def test_update_class_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/classes/999999", json={"name": "Nope"})

    assert response.status_code == 404


def test_delete_class(client: TestClient) -> None:
    grade_id = _create_grade(client, level=6)
    create_response = client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": "Delete Class"}
    )
    class_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/classes/{class_id}")

    assert response.status_code == 204


def test_delete_class_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/classes/999999")

    assert response.status_code == 404


def test_create_class_invalid_grade_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/classes/", json={"grade_id": 999999, "name": "Invalid FK Class"}
    )

    assert response.status_code == 422


def test_create_class_with_homeroom_room(client: TestClient) -> None:
    grade_id = _create_grade(client, level=8)
    room_response = client.post(
        "/api/v1/rooms/", json={"name": "Homeroom Room", "room_type": "普通教室"}
    )
    room_id = room_response.json()["id"]

    response = client.post(
        "/api/v1/classes/",
        json={
            "grade_id": grade_id,
            "name": "八年一班",
            "homeroom_room_id": room_id,
        },
    )

    assert response.status_code == 201
    assert response.json()["homeroom_room_id"] == room_id


def test_create_class_without_homeroom_room(client: TestClient) -> None:
    grade_id = _create_grade(client, level=9)

    response = client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": "九年一班"}
    )

    assert response.status_code == 201
    assert response.json()["homeroom_room_id"] is None


def test_delete_grade_blocked_by_dependent_class(client: TestClient) -> None:
    grade_id = _create_grade(client, level=7)
    client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": "Dependent Class"}
    )

    response = client.delete(f"/api/v1/grades/{grade_id}")

    assert response.status_code == 409
