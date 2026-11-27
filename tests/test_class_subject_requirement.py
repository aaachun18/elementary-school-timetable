from fastapi.testclient import TestClient
from tests.api_helpers import create_class, create_grade, create_record, mark_status


def _create_academic_year(client: TestClient, year: int) -> int:
    response = client.post("/api/v1/academic-years/", json={"year": year})
    academic_year_id: int = response.json()["id"]
    return academic_year_id


def _create_record(client: TestClient, year: int) -> int:
    """v3: a semester and its 尚未排課 record -- requirements belong to it."""
    academic_year_id = _create_academic_year(client, year)
    response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    )
    return create_record(client, response.json()["id"])


def _create_grade(client: TestClient, level: int) -> int:
    return create_grade(client, f"Grade {level}")


def _create_class(client: TestClient, level: int) -> int:
    grade_id = _create_grade(client, level)
    return create_class(client, grade_id, f"Class {level}")


def _create_subject(client: TestClient, name: str = "Subject A") -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    subject_id: int = response.json()["id"]
    return subject_id


def test_create_class_subject_requirement(client: TestClient) -> None:
    record_id = _create_record(client, year=2051)
    class_id = _create_class(client, level=1)
    subject_id = _create_subject(client)

    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 4,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["schedule_version_id"] == record_id
    assert data["class_id"] == class_id
    assert data["subject_id"] == subject_id
    assert data["weekly_periods"] == 4
    assert data["required_teacher_id"] is None
    assert data["required_room_id"] is None
    # Task 98: rooms have no types; the API no longer has the field.
    assert "required_room_type" not in data
    assert data["consecutive_limit"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_get_class_subject_requirement_list(client: TestClient) -> None:
    record_id = _create_record(client, year=2052)
    class_id = _create_class(client, level=2)
    subject_id = _create_subject(client)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
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
    record_id = _create_record(client, year=2053)
    class_id = _create_class(client, level=3)
    subject_id = _create_subject(client)
    create_response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
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
    record_id = _create_record(client, year=2054)
    class_id = _create_class(client, level=4)
    subject_id = _create_subject(client)
    create_response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
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
    record_id = _create_record(client, year=2055)
    class_id = _create_class(client, level=5)
    subject_id = _create_subject(client)
    create_response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
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
    record_id = _create_record(client, year=2056)
    class_id = _create_class(client, level=6)
    subject_id = _create_subject(client)
    payload = {
        "schedule_version_id": record_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "weekly_periods": 3,
    }
    client.post("/api/v1/class-subject-requirements/", json=payload)

    response = client.post("/api/v1/class-subject-requirements/", json=payload)

    assert response.status_code == 409


def test_create_class_subject_requirement_invalid_record_id(
    client: TestClient,
) -> None:
    class_id = _create_class(client, level=7)
    subject_id = _create_subject(client)

    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": 999999,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 3,
        },
    )

    assert response.status_code == 422


def test_create_class_subject_requirement_invalid_class_id(
    client: TestClient,
) -> None:
    record_id = _create_record(client, year=2057)
    subject_id = _create_subject(client)

    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": 999999,
            "subject_id": subject_id,
            "weekly_periods": 3,
        },
    )

    assert response.status_code == 422


def test_create_class_subject_requirement_invalid_subject_id(
    client: TestClient,
) -> None:
    record_id = _create_record(client, year=2058)
    class_id = _create_class(client, level=8)

    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_id,
            "subject_id": 999999,
            "weekly_periods": 3,
        },
    )

    assert response.status_code == 422


# --- Task 56: deleting a requirement takes its Lesson rows with it ---


def _create_requirement(
    client: TestClient,
    record_id: int,
    class_id: int,
    subject_id: int,
    weekly_periods: int,
) -> int:
    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": weekly_periods,
        },
    )
    requirement_id: int = response.json()["id"]
    return requirement_id


def _generate_lessons(client: TestClient, version_id: int) -> dict[int, list[int]]:
    """Returns {requirement_id: [lesson_id, ...]} for the lessons created."""
    response = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")
    assert response.status_code == 200
    lessons_by_requirement: dict[int, list[int]] = {}
    for item in response.json()["created_lessons"]:
        lessons_by_requirement.setdefault(
            item["class_subject_requirement_id"], []
        ).append(item["lesson_id"])
    return lessons_by_requirement


def test_delete_requirement_with_lessons(client: TestClient) -> None:
    record_id = _create_record(client, year=2061)
    class_id = _create_class(client, level=1)
    subject_id = _create_subject(client)
    requirement_id = _create_requirement(client, record_id, class_id, subject_id, 2)
    lesson_ids = _generate_lessons(client, record_id)[requirement_id]
    assert len(lesson_ids) == 2

    response = client.delete(f"/api/v1/class-subject-requirements/{requirement_id}")

    assert response.status_code == 204
    for lesson_id in lesson_ids:
        assert client.get(f"/api/v1/lessons/{lesson_id}").status_code == 404
    get_response = client.get(f"/api/v1/class-subject-requirements/{requirement_id}")
    assert get_response.status_code == 404
    # The record itself is not part of the requirement -- it stays.
    assert client.get(f"/api/v1/schedule-versions/{record_id}").status_code == 200


def test_delete_requirement_of_a_scheduled_record_is_refused(client: TestClient) -> None:
    """v3: a record with a timetable keeps its settings."""
    record_id = _create_record(client, year=2063)
    class_id = _create_class(client, level=3)
    subject_id = _create_subject(client)
    requirement_id = _create_requirement(client, record_id, class_id, subject_id, 2)
    lesson_ids = _generate_lessons(client, record_id)[requirement_id]
    mark_status(client, record_id, "AUTO", is_published=True)

    response = client.delete(f"/api/v1/class-subject-requirements/{requirement_id}")

    assert response.status_code == 409
    assert "尚未排課" in response.json()["detail"]
    get_response = client.get(f"/api/v1/class-subject-requirements/{requirement_id}")
    assert get_response.status_code == 200
    for lesson_id in lesson_ids:
        assert client.get(f"/api/v1/lessons/{lesson_id}").status_code == 200


def test_delete_requirement_leaves_other_requirements_untouched(
    client: TestClient,
) -> None:
    record_id = _create_record(client, year=2064)
    class_id = _create_class(client, level=4)
    subject_a_id = _create_subject(client, name="Subject A")
    subject_b_id = _create_subject(client, name="Subject B")
    requirement_a_id = _create_requirement(
        client, record_id, class_id, subject_a_id, 1
    )
    requirement_b_id = _create_requirement(
        client, record_id, class_id, subject_b_id, 2
    )
    lessons_by_requirement = _generate_lessons(client, record_id)
    lesson_b_ids = lessons_by_requirement[requirement_b_id]

    response = client.delete(f"/api/v1/class-subject-requirements/{requirement_a_id}")

    assert response.status_code == 204
    get_response = client.get(f"/api/v1/class-subject-requirements/{requirement_b_id}")
    assert get_response.status_code == 200
    for lesson_id in lesson_b_ids:
        assert client.get(f"/api/v1/lessons/{lesson_id}").status_code == 200


def test_same_class_and_subject_in_two_records_is_fine(client: TestClient) -> None:
    """v3: each record has its own requirements -- the uniqueness is per
    record."""
    first = _create_record(client, year=2065)
    semester_id = client.get(f"/api/v1/schedule-versions/{first}").json()["semester_id"]
    second = create_record(client, semester_id)
    class_id = _create_class(client, level=5)
    subject_id = _create_subject(client)

    for record_id in (first, second):
        response = client.post(
            "/api/v1/class-subject-requirements/",
            json={
                "schedule_version_id": record_id,
                "class_id": class_id,
                "subject_id": subject_id,
                "weekly_periods": 2,
            },
        )
        assert response.status_code == 201
