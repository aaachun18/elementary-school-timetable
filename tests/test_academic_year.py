from fastapi.testclient import TestClient


def test_create_academic_year(client: TestClient) -> None:
    response = client.post("/api/v1/academic-years/", json={"year": 2031})

    assert response.status_code == 201
    data = response.json()
    assert data["year"] == 2031
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_academic_year_cannot_set_is_active(client: TestClient) -> None:
    response = client.post(
        "/api/v1/academic-years/", json={"year": 2031, "is_active": False}
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_get_academic_year_list(client: TestClient) -> None:
    client.post("/api/v1/academic-years/", json={"year": 2032})

    response = client.get("/api/v1/academic-years/")

    assert response.status_code == 200
    years = [item["year"] for item in response.json()]
    assert 2032 in years


def test_get_academic_year_by_id(client: TestClient) -> None:
    create_response = client.post("/api/v1/academic-years/", json={"year": 2033})
    academic_year_id = create_response.json()["id"]

    response = client.get(f"/api/v1/academic-years/{academic_year_id}")

    assert response.status_code == 200
    assert response.json()["year"] == 2033


def test_get_academic_year_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/academic-years/999999")

    assert response.status_code == 404


def test_update_academic_year(client: TestClient) -> None:
    create_response = client.post("/api/v1/academic-years/", json={"year": 2034})
    academic_year_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/academic-years/{academic_year_id}", json={"is_active": False}
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_update_academic_year_not_found(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/academic-years/999999", json={"is_active": False}
    )

    assert response.status_code == 404


def test_delete_academic_year(client: TestClient) -> None:
    create_response = client.post("/api/v1/academic-years/", json={"year": 2035})
    academic_year_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/academic-years/{academic_year_id}")

    assert response.status_code == 204


def test_delete_academic_year_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/academic-years/999999")

    assert response.status_code == 404


def test_create_academic_year_duplicate_year_conflict(client: TestClient) -> None:
    client.post("/api/v1/academic-years/", json={"year": 2036})

    response = client.post("/api/v1/academic-years/", json={"year": 2036})

    assert response.status_code == 409
