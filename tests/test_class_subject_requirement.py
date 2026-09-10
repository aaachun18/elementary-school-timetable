from fastapi.testclient import TestClient


def _create_academic_year(client: TestClient, year: int) -> int:
    response = client.post("/api/v1/academic-years/", json={"year": year})
    academic_year_id: int = response.json()["id"]
    return academic_year_id


def _create_semester(client: TestClient, year: int) -> int:
    academic_year_id = _create_academic_year(client, year)
    response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    )
    semester_id: int = response.json()["id"]
    return semester_id


def _create_grade(client: TestClient, level: int) -> int:
    response = client.post(
        "/api/v1/grades/", json={"name": f"Grade {level}", "level": level}
    )
    grade_id: int = response.json()["id"]
    return grade_id


def _create_class(client: TestClient, level: int) -> int:
    grade_id = _create_grade(client, level)
    response = client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": f"Class {level}"}
    )
    class_id: int = response.json()["id"]
    return class_id


def _create_subject(client: TestClient, name: str = "Subject A") -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    subject_id: int = response.json()["id"]
    return subject_id


def test_create_class_subject_requirement(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2051)
    class_id = _create_class(client, level=1)
    subject_id = _create_subject(client)

    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 4,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["semester_id"] == semester_id
    assert data["class_id"] == class_id
    assert data["subject_id"] == subject_id
    assert data["weekly_periods"] == 4
    assert data["required_teacher_id"] is None
    assert data["required_room_type"] is None
    assert data["consecutive_limit"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_get_class_subject_requirement_list(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2052)
    class_id = _create_class(client, level=2)
    subject_id = _create_subject(client)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 3,
        },
    )

    response = client.get("/api/v1/class-subject-requirements/")

    assert response.status_code == 200
    periods = [item["weekly_periods"] for item in response.json()]
    assert 3 in periods


def test_get_class_subject_requirement_by_id(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2053)
    class_id = _create_class(client, level=3)
    subject_id = _create_subject(client)
    create_response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 5,
        },
    )
    requirement_id = create_response.json()["id"]

    response = client.get(f"/api/v1/class-subject-requirements/{requirement_id}")

    assert response.status_code == 200
    assert response.json()["weekly_periods"] == 5


def test_get_class_subject_requirement_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/class-subject-requirements/999999")

    assert response.status_code == 404


def test_update_class_subject_requirement(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2054)
    class_id = _create_class(client, level=4)
    subject_id = _create_subject(client)
    create_response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 2,
        },
    )
    requirement_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/class-subject-requirements/{requirement_id}",
        json={"weekly_periods": 6, "consecutive_limit": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["weekly_periods"] == 6
    assert data["consecutive_limit"] == 2


def test_update_class_subject_requirement_not_found(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/class-subject-requirements/999999", json={"weekly_periods": 1}
    )

    assert response.status_code == 404


def test_delete_class_subject_requirement(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2055)
    class_id = _create_class(client, level=5)
    subject_id = _create_subject(client)
    create_response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 3,
        },
    )
    requirement_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/class-subject-requirements/{requirement_id}")

    assert response.status_code == 204


def test_delete_class_subject_requirement_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/class-subject-requirements/999999")

    assert response.status_code == 404


def test_create_class_subject_requirement_duplicate_conflict(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=2056)
    class_id = _create_class(client, level=6)
    subject_id = _create_subject(client)
    payload = {
        "semester_id": semester_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "weekly_periods": 3,
    }
    client.post("/api/v1/class-subject-requirements/", json=payload)

    response = client.post("/api/v1/class-subject-requirements/", json=payload)

    assert response.status_code == 409


def test_create_class_subject_requirement_invalid_semester_id(
    client: TestClient,
) -> None:
    class_id = _create_class(client, level=7)
    subject_id = _create_subject(client)

    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": 999999,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 3,
        },
    )

    assert response.status_code == 422


def test_create_class_subject_requirement_invalid_class_id(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=2057)
    subject_id = _create_subject(client)

    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": 999999,
            "subject_id": subject_id,
            "weekly_periods": 3,
        },
    )

    assert response.status_code == 422


def test_create_class_subject_requirement_invalid_subject_id(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=2058)
    class_id = _create_class(client, level=8)

    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": 999999,
            "weekly_periods": 3,
        },
    )

    assert response.status_code == 422
