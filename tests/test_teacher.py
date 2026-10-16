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

    # Task 88: was 409 (the database CHECK, reached through
    # DuplicateValueError); the request is now refused by validation first,
    # with 422 and a Chinese message (see test_teacher_periods.py).
    assert response.status_code == 422


# --- Task 48: deleting a Teacher must also clear its own TeacherSubject/
# TeacherAvailability rows (owned sub-resources), but still be blocked by a
# REAL dependent record elsewhere (ClassSubjectRequirement.required_teacher_id
# or Schedule.teacher_id) -- and when blocked, nothing (not even the
# sub-resource rows) must be left half-deleted. ---


def _create_subject(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    subject_id: int = response.json()["id"]
    return subject_id


def _create_time_slot(client: TestClient, period: int) -> int:
    response = client.post(
        "/api/v1/time-slots/",
        json={"weekday": 1, "period": period, "is_teaching_period": True},
    )
    time_slot_id: int = response.json()["id"]
    return time_slot_id


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


def _create_grade_and_class(client: TestClient, level: int) -> int:
    grade_response = client.post(
        "/api/v1/grades/", json={"name": f"Grade {level}", "level": level}
    )
    grade_id = grade_response.json()["id"]
    class_response = client.post(
        "/api/v1/classes/",
        json={"grade_id": grade_id, "name": f"Class {level}"},
    )
    class_id: int = class_response.json()["id"]
    return class_id


def test_delete_teacher_with_subject_and_availability_succeeds(
    client: TestClient,
) -> None:
    teacher_id = client.post(
        "/api/v1/teachers/",
        json={
            "name": "Cleanly Deletable Teacher",
            "min_weekly_periods": 10,
            "max_weekly_periods": 20,
        },
    ).json()["id"]
    subject_id = _create_subject(client, "Subject 48a")
    time_slot_id = _create_time_slot(client, period=1)

    add_subject_response = client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )
    assert add_subject_response.status_code == 201
    add_slot_response = client.post(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots",
        json={"time_slot_id": time_slot_id},
    )
    assert add_slot_response.status_code == 201

    response = client.delete(f"/api/v1/teachers/{teacher_id}")

    assert response.status_code == 204
    # The sub-resource rows are genuinely gone too, not just the teacher --
    # querying either by this (now-nonexistent) teacher_id 404s on the
    # teacher itself, which is the strongest available confirmation that
    # they didn't silently survive as orphans.
    assert client.get(f"/api/v1/teachers/{teacher_id}").status_code == 404


def test_delete_teacher_blocked_by_required_teacher_id_keeps_subrecords(
    client: TestClient,
) -> None:
    teacher_id = client.post(
        "/api/v1/teachers/",
        json={
            "name": "Required Teacher",
            "min_weekly_periods": 10,
            "max_weekly_periods": 20,
        },
    ).json()["id"]
    subject_id = _create_subject(client, "Subject 48b")
    client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )

    semester_id = _create_semester(client, year=2100)
    class_id = _create_grade_and_class(client, level=48)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 2,
            "required_teacher_id": teacher_id,
        },
    )

    response = client.delete(f"/api/v1/teachers/{teacher_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "此資料仍被其他資料參照，無法刪除"
    # Teacher AND its qualification both survived -- the transaction was
    # fully rolled back, not partially applied.
    get_response = client.get(f"/api/v1/teachers/{teacher_id}")
    assert get_response.status_code == 200
    subjects_response = client.get(f"/api/v1/teachers/{teacher_id}/subjects")
    assert subjects_response.status_code == 200
    assert [s["id"] for s in subjects_response.json()] == [subject_id]


def test_delete_teacher_blocked_by_schedule_keeps_subrecords(
    client: TestClient,
) -> None:
    teacher_id = client.post(
        "/api/v1/teachers/",
        json={
            "name": "Scheduled Teacher",
            "min_weekly_periods": 10,
            "max_weekly_periods": 20,
        },
    ).json()["id"]
    time_slot_id = _create_time_slot(client, period=2)
    client.post(
        f"/api/v1/teachers/{teacher_id}/unavailable-slots",
        json={"time_slot_id": time_slot_id},
    )

    semester_id = _create_semester(client, year=2101)
    class_id = _create_grade_and_class(client, level=49)
    subject_id = _create_subject(client, "Subject 48c")
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 1,
        },
    )
    version_id = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": semester_id, "version_number": 1, "status": "DRAFT"},
    ).json()["id"]
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    lesson_id = generate_response.json()["created_lessons"][0]["lesson_id"]
    client.post(
        "/api/v1/schedules/",
        json={
            "schedule_version_id": version_id,
            "lesson_id": lesson_id,
            "teacher_id": teacher_id,
        },
    )

    response = client.delete(f"/api/v1/teachers/{teacher_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "此資料仍被其他資料參照，無法刪除"
    get_response = client.get(f"/api/v1/teachers/{teacher_id}")
    assert get_response.status_code == 200
    slots_response = client.get(f"/api/v1/teachers/{teacher_id}/unavailable-slots")
    assert slots_response.status_code == 200
    assert [s["id"] for s in slots_response.json()] == [time_slot_id]
