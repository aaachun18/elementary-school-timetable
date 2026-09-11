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


def _create_requirement(
    client: TestClient,
    semester_id: int,
    class_id: int,
    subject_id: int,
    weekly_periods: int,
) -> int:
    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": weekly_periods,
        },
    )
    requirement_id: int = response.json()["id"]
    return requirement_id


def _create_schedule_version(client: TestClient, semester_id: int) -> int:
    response = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": semester_id, "version_number": 1, "status": "DRAFT"},
    )
    version_id: int = response.json()["id"]
    return version_id


# --- Standard CRUD ---


def test_create_schedule_version(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2061)

    response = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": semester_id, "version_number": 1, "status": "DRAFT"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["semester_id"] == semester_id
    assert data["version_number"] == 1
    assert data["status"] == "DRAFT"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_schedule_version_invalid_status_returns_422(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=2062)

    response = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": semester_id, "version_number": 1, "status": "ARCHIVED"},
    )

    assert response.status_code == 422


def test_create_schedule_version_duplicate_version_number_conflict(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=2071)
    payload = {
        "semester_id": semester_id,
        "version_number": 1,
        "status": "DRAFT",
    }
    client.post("/api/v1/schedule-versions/", json=payload)

    response = client.post("/api/v1/schedule-versions/", json=payload)

    assert response.status_code == 409


def test_get_schedule_version_list(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2063)
    _create_schedule_version(client, semester_id)

    response = client.get("/api/v1/schedule-versions/")

    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_schedule_version_by_id(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2064)
    version_id = _create_schedule_version(client, semester_id)

    response = client.get(f"/api/v1/schedule-versions/{version_id}")

    assert response.status_code == 200
    assert response.json()["id"] == version_id


def test_get_schedule_version_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/schedule-versions/999999")

    assert response.status_code == 404


def test_update_schedule_version(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2065)
    version_id = _create_schedule_version(client, semester_id)

    response = client.patch(
        f"/api/v1/schedule-versions/{version_id}", json={"status": "PUBLISHED"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"


def test_update_schedule_version_not_found(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/schedule-versions/999999", json={"status": "PUBLISHED"}
    )

    assert response.status_code == 404


def test_delete_schedule_version(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2066)
    version_id = _create_schedule_version(client, semester_id)

    response = client.delete(f"/api/v1/schedule-versions/{version_id}")

    assert response.status_code == 204


def test_delete_schedule_version_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/schedule-versions/999999")

    assert response.status_code == 404


# --- generate-lessons (diff sync) ---


def test_generate_lessons_creates_missing_lessons(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2067)
    class_id = _create_class(client, level=10)
    subject_id = _create_subject(client, name="Math 2067")
    _create_requirement(client, semester_id, class_id, subject_id, weekly_periods=3)
    version_id = _create_schedule_version(client, semester_id)

    response = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 3
    assert len(data["created_lessons"]) == 3
    sequence_numbers = sorted(
        lesson["sequence_number"] for lesson in data["created_lessons"]
    )
    assert sequence_numbers == [1, 2, 3]

    lessons_response = client.get("/api/v1/lessons/")
    assert lessons_response.status_code == 200
    assert len(lessons_response.json()) == 3


def test_generate_lessons_is_idempotent_when_already_synced(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=2068)
    class_id = _create_class(client, level=11)
    subject_id = _create_subject(client, name="Math 2068")
    _create_requirement(client, semester_id, class_id, subject_id, weekly_periods=2)
    version_id = _create_schedule_version(client, semester_id)

    first = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")
    assert first.json()["created_count"] == 2

    second = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    assert second.status_code == 200
    assert second.json()["created_count"] == 0


def test_generate_lessons_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/schedule-versions/999999/generate-lessons")

    assert response.status_code == 404


def test_generate_lessons_over_provisioned_returns_409_and_creates_nothing(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=2069)
    class_id = _create_class(client, level=12)
    subject_id = _create_subject(client, name="Math 2069")
    requirement_id = _create_requirement(
        client, semester_id, class_id, subject_id, weekly_periods=3
    )
    version_id = _create_schedule_version(client, semester_id)

    # Sync to 3 lessons first.
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    # Shrink the requirement to 1 weekly period -- the existing 3 lessons
    # now exceed it.
    client.patch(
        f"/api/v1/class-subject-requirements/{requirement_id}",
        json={"weekly_periods": 1},
    )

    response = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    assert response.status_code == 409
    over_provisioned = response.json()["over_provisioned"]
    assert len(over_provisioned) == 1
    assert over_provisioned[0]["class_subject_requirement_id"] == requirement_id
    assert over_provisioned[0]["weekly_periods"] == 1
    assert over_provisioned[0]["existing_lesson_count"] == 3

    # Nothing was auto-deleted.
    lessons_response = client.get("/api/v1/lessons/")
    assert len(lessons_response.json()) == 3


def test_generate_lessons_over_provisioned_blocks_other_requirements_too(
    client: TestClient,
) -> None:
    """One over-provisioned requirement aborts the WHOLE call atomically --
    a different, genuinely under-provisioned requirement in the same
    semester gets nothing created either, in that same call."""
    semester_id = _create_semester(client, year=2070)
    class_id = _create_class(client, level=13)
    subject_a = _create_subject(client, name="Subject A 2070")
    subject_b = _create_subject(client, name="Subject B 2070")
    requirement_a = _create_requirement(
        client, semester_id, class_id, subject_a, weekly_periods=2
    )
    _create_requirement(client, semester_id, class_id, subject_b, weekly_periods=2)
    version_id = _create_schedule_version(client, semester_id)

    # Sync both requirements to 2 lessons each.
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    # Requirement A becomes over-provisioned.
    client.patch(
        f"/api/v1/class-subject-requirements/{requirement_a}",
        json={"weekly_periods": 1},
    )

    # A brand-new requirement C that genuinely needs lessons.
    subject_c = _create_subject(client, name="Subject C 2070")
    _create_requirement(client, semester_id, class_id, subject_c, weekly_periods=2)

    response = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    assert response.status_code == 409

    # Requirement C got nothing, even though it was legitimately short.
    lessons_response = client.get("/api/v1/lessons/")
    assert len(lessons_response.json()) == 4  # only the original 2 + 2


# --- Task 25: PUBLISHED version lock ---


def _publish(client: TestClient, version_id: int) -> None:
    response = client.patch(
        f"/api/v1/schedule-versions/{version_id}", json={"status": "PUBLISHED"}
    )
    assert response.status_code == 200


def test_update_published_schedule_version_returns_409(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2072)
    version_id = _create_schedule_version(client, semester_id)
    _publish(client, version_id)

    response = client.patch(
        f"/api/v1/schedule-versions/{version_id}", json={"version_number": 2}
    )

    assert response.status_code == 409
    # Confirm it genuinely wasn't changed.
    get_response = client.get(f"/api/v1/schedule-versions/{version_id}")
    assert get_response.json()["version_number"] == 1


def test_unpublish_published_schedule_version_returns_409(client: TestClient) -> None:
    """Changing status itself -- even back to DRAFT -- is locked too, not
    just "other fields while status stays PUBLISHED"."""
    semester_id = _create_semester(client, year=2073)
    version_id = _create_schedule_version(client, semester_id)
    _publish(client, version_id)

    response = client.patch(
        f"/api/v1/schedule-versions/{version_id}", json={"status": "DRAFT"}
    )

    assert response.status_code == 409
    get_response = client.get(f"/api/v1/schedule-versions/{version_id}")
    assert get_response.json()["status"] == "PUBLISHED"


def test_generate_lessons_on_published_version_returns_409(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2074)
    class_id = _create_class(client, level=14)
    subject_id = _create_subject(client, name="Math 2074")
    _create_requirement(client, semester_id, class_id, subject_id, weekly_periods=2)
    version_id = _create_schedule_version(client, semester_id)
    _publish(client, version_id)

    response = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    assert response.status_code == 409
    # Confirm nothing was created.
    lessons_response = client.get("/api/v1/lessons/")
    assert lessons_response.json() == []


def test_run_scheduler_on_published_version_returns_409(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2075)
    class_id = _create_class(client, level=15)
    subject_id = _create_subject(client, name="Math 2075")
    _create_requirement(client, semester_id, class_id, subject_id, weekly_periods=1)
    version_id = _create_schedule_version(client, semester_id)
    # generate-lessons must happen BEFORE publishing -- it's locked too.
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")
    _publish(client, version_id)

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    # No Schedule rows exist yet at this point, so a 409 here can only come
    # from the PUBLISHED lock, not from the (separate) already-scheduled
    # guard -- confirms the lock is checked even when there's nothing to
    # protect from being overwritten.
    assert response.status_code == 409
    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


def test_draft_schedule_version_update_still_works(client: TestClient) -> None:
    """Regression guard: the PUBLISHED lock must not affect ordinary DRAFT
    updates."""
    semester_id = _create_semester(client, year=2076)
    version_id = _create_schedule_version(client, semester_id)

    response = client.patch(
        f"/api/v1/schedule-versions/{version_id}", json={"version_number": 5}
    )

    assert response.status_code == 200
    assert response.json()["version_number"] == 5
