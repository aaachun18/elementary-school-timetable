from fastapi.testclient import TestClient


def _create_teacher(client: TestClient, name: str = "Teacher A") -> int:
    response = client.post(
        "/api/v1/teachers/",
        json={"name": name, "min_weekly_periods": 10, "max_weekly_periods": 20},
    )
    teacher_id: int = response.json()["id"]
    return teacher_id


def _create_subject(client: TestClient, name: str = "Subject A") -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    subject_id: int = response.json()["id"]
    return subject_id


def test_add_teacher_subject(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    subject_id = _create_subject(client)

    response = client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == subject_id
    assert data["name"] == "Subject A"


def test_list_teacher_subjects(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    subject_id = _create_subject(client)
    client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )

    response = client.get(f"/api/v1/teachers/{teacher_id}/subjects")

    assert response.status_code == 200
    subject_ids = [item["id"] for item in response.json()]
    assert subject_id in subject_ids


def test_add_teacher_subject_duplicate_conflict(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    subject_id = _create_subject(client)
    client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )

    response = client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )

    assert response.status_code == 409


def test_add_teacher_subject_invalid_teacher_id(client: TestClient) -> None:
    subject_id = _create_subject(client)

    response = client.post(
        "/api/v1/teachers/999999/subjects", json={"subject_id": subject_id}
    )

    assert response.status_code == 422


def test_add_teacher_subject_invalid_subject_id(client: TestClient) -> None:
    teacher_id = _create_teacher(client)

    response = client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": 999999}
    )

    assert response.status_code == 422


def test_list_teacher_subjects_teacher_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/teachers/999999/subjects")

    assert response.status_code == 404


def test_remove_teacher_subject(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    subject_id = _create_subject(client)
    client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )

    response = client.delete(f"/api/v1/teachers/{teacher_id}/subjects/{subject_id}")

    assert response.status_code == 204


def test_remove_teacher_subject_not_found(client: TestClient) -> None:
    teacher_id = _create_teacher(client)
    subject_id = _create_subject(client)
    client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )
    client.delete(f"/api/v1/teachers/{teacher_id}/subjects/{subject_id}")

    response = client.delete(f"/api/v1/teachers/{teacher_id}/subjects/{subject_id}")

    assert response.status_code == 404
