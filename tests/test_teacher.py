from fastapi.testclient import TestClient


def test_create_teacher(client: TestClient) -> None:
    response = client.post(
        "/api/v1/teachers/",
        json={"name": "Teacher A", "min_weekly_periods": 10, "max_weekly_periods": 20},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Teacher A"
    assert data["is_active"] is True
    assert data["min_weekly_periods"] == 10
    assert data["max_weekly_periods"] == 20
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_teacher_cannot_set_is_active(client: TestClient) -> None:
    response = client.post(
        "/api/v1/teachers/",
        json={
            "name": "Teacher A",
            "min_weekly_periods": 10,
            "max_weekly_periods": 20,
            "is_active": False,
        },
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_get_teacher_list(client: TestClient) -> None:
    client.post(
        "/api/v1/teachers/",
        json={
            "name": "List Teacher",
            "min_weekly_periods": 10,
            "max_weekly_periods": 20,
        },
    )

    response = client.get("/api/v1/teachers/")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "List Teacher" in names


def test_get_teacher_by_id(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/teachers/",
        json={
            "name": "Get Teacher",
            "min_weekly_periods": 10,
            "max_weekly_periods": 20,
        },
    )
    teacher_id = create_response.json()["id"]

    response = client.get(f"/api/v1/teachers/{teacher_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Get Teacher"


def test_get_teacher_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/teachers/999999")

    assert response.status_code == 404


def test_update_teacher(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/teachers/",
        json={
            "name": "Old Teacher",
            "min_weekly_periods": 10,
            "max_weekly_periods": 20,
        },
    )
    teacher_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/teachers/{teacher_id}", json={"name": "New Teacher"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Teacher"


def test_update_teacher_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/teachers/999999", json={"name": "Nope"})

    assert response.status_code == 404


def test_delete_teacher(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/teachers/",
        json={
            "name": "Delete Teacher",
            "min_weekly_periods": 10,
            "max_weekly_periods": 20,
        },
    )
    teacher_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/teachers/{teacher_id}")

    assert response.status_code == 204


def test_delete_teacher_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/teachers/999999")

    assert response.status_code == 404


def test_create_teacher_weekly_periods_check_violation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/teachers/",
        json={
            "name": "Bad Teacher",
            "min_weekly_periods": 20,
            "max_weekly_periods": 15,
        },
    )

    assert response.status_code == 409
