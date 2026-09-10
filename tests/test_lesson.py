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


def _create_subject(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    subject_id: int = response.json()["id"]
    return subject_id


def _generate_lessons(
    client: TestClient, year: int, weekly_periods: int
) -> list[int]:
    """Creates one requirement + syncs it, returning the created lesson ids."""
    semester_id = _create_semester(client, year)
    class_id = _create_class(client, level=year % 1000)
    subject_id = _create_subject(client, name=f"Subject {year}")
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": weekly_periods,
        },
    )
    version_response = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": semester_id, "version_number": 1, "status": "DRAFT"},
    )
    version_id = version_response.json()["id"]
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    return [
        lesson["lesson_id"] for lesson in generate_response.json()["created_lessons"]
    ]


def test_list_lessons(client: TestClient) -> None:
    lesson_ids = _generate_lessons(client, year=2091, weekly_periods=2)

    response = client.get("/api/v1/lessons/")

    assert response.status_code == 200
    returned_ids = [item["id"] for item in response.json()]
    for lesson_id in lesson_ids:
        assert lesson_id in returned_ids


def test_get_lesson_by_id(client: TestClient) -> None:
    lesson_ids = _generate_lessons(client, year=2092, weekly_periods=1)
    lesson_id = lesson_ids[0]

    response = client.get(f"/api/v1/lessons/{lesson_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == lesson_id
    assert data["sequence_number"] == 1


def test_get_lesson_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/lessons/999999")

    assert response.status_code == 404
