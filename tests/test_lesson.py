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


def _create_time_slot(client: TestClient, weekday: int, period: int) -> int:
    response = client.post(
        "/api/v1/time-slots/", json={"weekday": weekday, "period": period}
    )
    time_slot_id: int = response.json()["id"]
    return time_slot_id


# --- fix-time-slot (Task 28) ---


def test_fix_lesson_time_slot_sets_and_clears(client: TestClient) -> None:
    lesson_ids = _generate_lessons(client, year=2093, weekly_periods=1)
    lesson_id = lesson_ids[0]
    time_slot_id = _create_time_slot(client, weekday=3, period=3)

    set_response = client.patch(
        f"/api/v1/lessons/{lesson_id}/fix-time-slot",
        json={"time_slot_id": time_slot_id},
    )
    assert set_response.status_code == 200
    assert set_response.json()["fixed_time_slot_id"] == time_slot_id

    get_response = client.get(f"/api/v1/lessons/{lesson_id}")
    assert get_response.json()["fixed_time_slot_id"] == time_slot_id

    clear_response = client.patch(
        f"/api/v1/lessons/{lesson_id}/fix-time-slot",
        json={"time_slot_id": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["fixed_time_slot_id"] is None


def test_fix_lesson_time_slot_not_found(client: TestClient) -> None:
    time_slot_id = _create_time_slot(client, weekday=1, period=1)

    response = client.patch(
        "/api/v1/lessons/999999/fix-time-slot",
        json={"time_slot_id": time_slot_id},
    )

    assert response.status_code == 404


def test_fix_lesson_time_slot_invalid_time_slot_id(client: TestClient) -> None:
    lesson_ids = _generate_lessons(client, year=2094, weekly_periods=1)
    lesson_id = lesson_ids[0]

    response = client.patch(
        f"/api/v1/lessons/{lesson_id}/fix-time-slot",
        json={"time_slot_id": 999999},
    )

    assert response.status_code == 422


def test_fix_lesson_time_slot_forbidden_for_teacher(
    client: TestClient, teacher_client: TestClient
) -> None:
    lesson_ids = _generate_lessons(client, year=2095, weekly_periods=1)
    lesson_id = lesson_ids[0]
    time_slot_id = _create_time_slot(client, weekday=2, period=2)

    response = teacher_client.patch(
        f"/api/v1/lessons/{lesson_id}/fix-time-slot",
        json={"time_slot_id": time_slot_id},
    )

    assert response.status_code == 403
