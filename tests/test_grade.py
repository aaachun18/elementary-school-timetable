from fastapi.testclient import TestClient


def test_create_grade(client: TestClient) -> None:
    response = client.post("/api/v1/grades/", json={"name": "1年級", "level": 1})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "1年級"
    assert data["level"] == 1
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_get_grade_list(client: TestClient) -> None:
    client.post("/api/v1/grades/", json={"name": "List Grade", "level": 2})

    response = client.get("/api/v1/grades/")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "List Grade" in names


def test_get_grade_by_id(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/grades/", json={"name": "Get Grade", "level": 3}
    )
    grade_id = create_response.json()["id"]

    response = client.get(f"/api/v1/grades/{grade_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Get Grade"


def test_get_grade_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/grades/999999")

    assert response.status_code == 404


def test_update_grade(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/grades/", json={"name": "Old Grade", "level": 4}
    )
    grade_id = create_response.json()["id"]

    response = client.patch(f"/api/v1/grades/{grade_id}", json={"name": "New Grade"})

    assert response.status_code == 200
    assert response.json()["name"] == "New Grade"


def test_update_grade_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/grades/999999", json={"name": "Nope"})

    assert response.status_code == 404


def test_delete_grade(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/grades/", json={"name": "Delete Grade", "level": 5}
    )
    grade_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/grades/{grade_id}")

    assert response.status_code == 204


def test_delete_grade_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/grades/999999")

    assert response.status_code == 404


def test_create_grade_duplicate_level_conflict(client: TestClient) -> None:
    client.post("/api/v1/grades/", json={"name": "Grade A", "level": 6})

    response = client.post("/api/v1/grades/", json={"name": "Grade B", "level": 6})

    assert response.status_code == 409
