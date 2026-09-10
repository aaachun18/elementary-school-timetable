from fastapi.testclient import TestClient


def _create_academic_year(client: TestClient, year: int) -> int:
    response = client.post("/api/v1/academic-years/", json={"year": year})
    academic_year_id: int = response.json()["id"]
    return academic_year_id


def test_create_semester(client: TestClient) -> None:
    academic_year_id = _create_academic_year(client, year=2041)

    response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["academic_year_id"] == academic_year_id
    assert data["number"] == 1
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_semester_cannot_set_is_active(client: TestClient) -> None:
    academic_year_id = _create_academic_year(client, year=2042)

    response = client.post(
        "/api/v1/semesters/",
        json={
            "academic_year_id": academic_year_id,
            "number": 1,
            "is_active": False,
        },
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_get_semester_list(client: TestClient) -> None:
    academic_year_id = _create_academic_year(client, year=2043)
    client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 2},
    )

    response = client.get("/api/v1/semesters/")

    assert response.status_code == 200
    numbers = [item["number"] for item in response.json()]
    assert 2 in numbers


def test_get_semester_by_id(client: TestClient) -> None:
    academic_year_id = _create_academic_year(client, year=2044)
    create_response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    )
    semester_id = create_response.json()["id"]

    response = client.get(f"/api/v1/semesters/{semester_id}")

    assert response.status_code == 200
    assert response.json()["academic_year_id"] == academic_year_id


def test_get_semester_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/semesters/999999")

    assert response.status_code == 404


def test_update_semester(client: TestClient) -> None:
    academic_year_id = _create_academic_year(client, year=2045)
    create_response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    )
    semester_id = create_response.json()["id"]

    response = client.patch(f"/api/v1/semesters/{semester_id}", json={"number": 2})

    assert response.status_code == 200
    assert response.json()["number"] == 2


def test_update_semester_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/semesters/999999", json={"number": 2})

    assert response.status_code == 404


def test_delete_semester(client: TestClient) -> None:
    academic_year_id = _create_academic_year(client, year=2046)
    create_response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    )
    semester_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/semesters/{semester_id}")

    assert response.status_code == 204


def test_delete_semester_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/semesters/999999")

    assert response.status_code == 404


def test_create_semester_number_check_violation(client: TestClient) -> None:
    academic_year_id = _create_academic_year(client, year=2047)

    response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 3},
    )

    assert response.status_code == 409


def test_create_semester_invalid_academic_year_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/semesters/", json={"academic_year_id": 999999, "number": 1}
    )

    assert response.status_code == 422
