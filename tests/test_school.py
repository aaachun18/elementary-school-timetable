from fastapi.testclient import TestClient


def test_create_school(client: TestClient) -> None:
    response = client.post("/api/v1/schools/", json={"name": "Test School"})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test School"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_school_cannot_set_is_active(client: TestClient) -> None:
    response = client.post(
        "/api/v1/schools/", json={"name": "Test School", "is_active": False}
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_get_school_list(client: TestClient) -> None:
    client.post("/api/v1/schools/", json={"name": "List Test School"})

    response = client.get("/api/v1/schools/")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "List Test School" in names


def test_get_school_by_id(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/schools/", json={"name": "Get Test School"}
    )
    school_id = create_response.json()["id"]

    response = client.get(f"/api/v1/schools/{school_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Get Test School"


def test_get_school_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/schools/999999")

    assert response.status_code == 404


def test_update_school(client: TestClient) -> None:
    create_response = client.post("/api/v1/schools/", json={"name": "Old Name"})
    school_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/schools/{school_id}", json={"name": "New Name"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_update_school_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/schools/999999", json={"name": "Nope"})

    assert response.status_code == 404


def test_delete_school(client: TestClient) -> None:
    create_response = client.post("/api/v1/schools/", json={"name": "Delete Me"})
    school_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/schools/{school_id}")

    assert response.status_code == 204


def test_delete_school_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/schools/999999")

    assert response.status_code == 404
