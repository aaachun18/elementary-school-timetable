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


def _create_teacher(client: TestClient, name: str) -> int:
    response = client.post(
        "/api/v1/teachers/",
        json={"name": name, "min_weekly_periods": 1, "max_weekly_periods": 20},
    )
    teacher_id: int = response.json()["id"]
    return teacher_id


def _create_time_slot(client: TestClient, period: int) -> int:
    response = client.post(
        "/api/v1/time-slots/",
        json={"weekday": 1, "period": period, "is_teaching_period": True},
    )
    time_slot_id: int = response.json()["id"]
    return time_slot_id


def _create_room(client: TestClient, name: str) -> int:
    response = client.post(
        "/api/v1/rooms/", json={"name": name, "room_type": "普通教室"}
    )
    room_id: int = response.json()["id"]
    return room_id


def _create_lesson(client: TestClient, year: int) -> tuple[int, int]:
    """Returns (lesson_id, schedule_version_id) for a freshly-synced,
    single-lesson requirement."""
    semester_id = _create_semester(client, year)
    class_id = _create_class(client, level=year % 1000)
    subject_id = _create_subject(client, name=f"Subject {year}")
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 1,
        },
    )
    version_response = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": semester_id, "version_number": 1, "status": "DRAFT"},
    )
    version_id: int = version_response.json()["id"]
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    lesson_id: int = generate_response.json()["created_lessons"][0]["lesson_id"]
    return lesson_id, version_id


def test_create_schedule(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2081)

    response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": lesson_id},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["schedule_version_id"] == version_id
    assert data["lesson_id"] == lesson_id
    assert data["teacher_id"] is None
    assert data["time_slot_id"] is None
    assert data["room_id"] is None
    assert "id" in data


def test_create_schedule_with_full_assignment(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2082)
    teacher_id = _create_teacher(client, "Schedule Teacher 2082")
    time_slot_id = _create_time_slot(client, period=1)
    room_id = _create_room(client, "Schedule Room 2082")

    response = client.post(
        "/api/v1/schedules/",
        json={
            "schedule_version_id": version_id,
            "lesson_id": lesson_id,
            "teacher_id": teacher_id,
            "time_slot_id": time_slot_id,
            "room_id": room_id,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["teacher_id"] == teacher_id
    assert data["time_slot_id"] == time_slot_id
    assert data["room_id"] == room_id


def test_get_schedule_list(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2083)
    client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": lesson_id},
    )

    response = client.get("/api/v1/schedules/")

    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_schedule_by_id(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2084)
    create_response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": lesson_id},
    )
    schedule_id = create_response.json()["id"]

    response = client.get(f"/api/v1/schedules/{schedule_id}")

    assert response.status_code == 200
    assert response.json()["id"] == schedule_id


def test_get_schedule_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/schedules/999999")

    assert response.status_code == 404


def test_update_schedule(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2085)
    create_response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": lesson_id},
    )
    schedule_id = create_response.json()["id"]
    time_slot_id = _create_time_slot(client, period=2)

    response = client.patch(
        f"/api/v1/schedules/{schedule_id}", json={"time_slot_id": time_slot_id}
    )

    assert response.status_code == 200
    assert response.json()["time_slot_id"] == time_slot_id


def test_update_schedule_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/schedules/999999", json={"time_slot_id": 1})

    assert response.status_code == 404


def test_delete_schedule(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2086)
    create_response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": lesson_id},
    )
    schedule_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/schedules/{schedule_id}")

    assert response.status_code == 204


def test_delete_schedule_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/schedules/999999")

    assert response.status_code == 404


def test_create_schedule_duplicate_version_lesson_conflict(
    client: TestClient,
) -> None:
    lesson_id, version_id = _create_lesson(client, year=2087)
    payload = {"schedule_version_id": version_id, "lesson_id": lesson_id}
    client.post("/api/v1/schedules/", json=payload)

    response = client.post("/api/v1/schedules/", json=payload)

    assert response.status_code == 409


def test_create_schedule_invalid_lesson_id(client: TestClient) -> None:
    _, version_id = _create_lesson(client, year=2088)

    response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": 999999},
    )

    assert response.status_code == 422


def test_create_schedule_invalid_schedule_version_id(client: TestClient) -> None:
    lesson_id, _ = _create_lesson(client, year=2089)

    response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": 999999, "lesson_id": lesson_id},
    )

    assert response.status_code == 422


# --- Task 25: PUBLISHED version lock ---


def _publish_schedule_version(client: TestClient, version_id: int) -> None:
    response = client.patch(
        f"/api/v1/schedule-versions/{version_id}", json={"status": "PUBLISHED"}
    )
    assert response.status_code == 200


def test_create_schedule_blocked_when_version_published(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2094)
    _publish_schedule_version(client, version_id)

    response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": lesson_id},
    )

    assert response.status_code == 409
    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


def test_update_schedule_blocked_when_version_published(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2091)
    create_response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": lesson_id},
    )
    schedule_id = create_response.json()["id"]
    time_slot_id = _create_time_slot(client, period=3)
    _publish_schedule_version(client, version_id)

    response = client.patch(
        f"/api/v1/schedules/{schedule_id}", json={"time_slot_id": time_slot_id}
    )

    assert response.status_code == 409
    get_response = client.get(f"/api/v1/schedules/{schedule_id}")
    assert get_response.json()["time_slot_id"] is None


def test_delete_schedule_blocked_when_version_published(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2092)
    create_response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": lesson_id},
    )
    schedule_id = create_response.json()["id"]
    _publish_schedule_version(client, version_id)

    response = client.delete(f"/api/v1/schedules/{schedule_id}")

    assert response.status_code == 409
    get_response = client.get(f"/api/v1/schedules/{schedule_id}")
    assert get_response.status_code == 200  # never deleted


def test_update_schedule_still_works_when_version_draft(client: TestClient) -> None:
    """Regression guard: the PUBLISHED lock must not affect an ordinary
    Schedule update under a DRAFT version."""
    lesson_id, version_id = _create_lesson(client, year=2093)
    create_response = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": version_id, "lesson_id": lesson_id},
    )
    schedule_id = create_response.json()["id"]
    time_slot_id = _create_time_slot(client, period=4)

    response = client.patch(
        f"/api/v1/schedules/{schedule_id}", json={"time_slot_id": time_slot_id}
    )

    assert response.status_code == 200
    assert response.json()["time_slot_id"] == time_slot_id


def test_create_schedule_invalid_teacher_id(client: TestClient) -> None:
    lesson_id, version_id = _create_lesson(client, year=2090)

    response = client.post(
        "/api/v1/schedules/",
        json={
            "schedule_version_id": version_id,
            "lesson_id": lesson_id,
            "teacher_id": 999999,
        },
    )

    assert response.status_code == 422
