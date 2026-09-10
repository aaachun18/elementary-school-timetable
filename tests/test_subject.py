from fastapi.testclient import TestClient


def test_create_subject(client: TestClient) -> None:
    response = client.post("/api/v1/subjects/", json={"name": "數學"})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "數學"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_subject_cannot_set_is_active(client: TestClient) -> None:
    response = client.post(
        "/api/v1/subjects/", json={"name": "數學", "is_active": False}
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_get_subject_list(client: TestClient) -> None:
    client.post("/api/v1/subjects/", json={"name": "List Subject"})

    response = client.get("/api/v1/subjects/")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "List Subject" in names


def test_get_subject_by_id(client: TestClient) -> None:
    create_response = client.post("/api/v1/subjects/", json={"name": "Get Subject"})
    subject_id = create_response.json()["id"]

    response = client.get(f"/api/v1/subjects/{subject_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Get Subject"


def test_get_subject_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/subjects/999999")

    assert response.status_code == 404


def test_update_subject(client: TestClient) -> None:
    create_response = client.post("/api/v1/subjects/", json={"name": "Old Subject"})
    subject_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/subjects/{subject_id}", json={"name": "New Subject"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Subject"


def test_update_subject_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/subjects/999999", json={"name": "Nope"})

    assert response.status_code == 404


def test_delete_subject(client: TestClient) -> None:
    create_response = client.post("/api/v1/subjects/", json={"name": "Delete Subject"})
    subject_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/subjects/{subject_id}")

    assert response.status_code == 204


def test_delete_subject_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/subjects/999999")

    assert response.status_code == 404


def test_create_subject_duplicate_name_conflict(client: TestClient) -> None:
    client.post("/api/v1/subjects/", json={"name": "重複科目"})

    response = client.post("/api/v1/subjects/", json={"name": "重複科目"})

    assert response.status_code == 409
