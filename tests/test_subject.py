from fastapi.testclient import TestClient


def test_create_subject(client: TestClient) -> None:
    response = client.post("/api/v1/subjects/", json={"name": "數學"})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "數學"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_subject_cannot_set_is_active(client: TestClient) -> None:
    response = client.post(
        "/api/v1/subjects/", json={"name": "數學", "is_active": False}
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_get_subject_list(client: TestClient) -> None:
    client.post("/api/v1/subjects/", json={"name": "List Subject"})

    response = client.get("/api/v1/subjects/")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "List Subject" in names


def test_get_subject_by_id(client: TestClient) -> None:
    create_response = client.post("/api/v1/subjects/", json={"name": "Get Subject"})
    subject_id = create_response.json()["id"]

    response = client.get(f"/api/v1/subjects/{subject_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Get Subject"


def test_get_subject_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/subjects/999999")

    assert response.status_code == 404


def test_update_subject(client: TestClient) -> None:
    create_response = client.post("/api/v1/subjects/", json={"name": "Old Subject"})
    subject_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/subjects/{subject_id}", json={"name": "New Subject"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Subject"


def test_update_subject_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/subjects/999999", json={"name": "Nope"})

    assert response.status_code == 404


def test_delete_subject(client: TestClient) -> None:
    create_response = client.post("/api/v1/subjects/", json={"name": "Delete Subject"})
    subject_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/subjects/{subject_id}")

    assert response.status_code == 204


def test_delete_subject_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/subjects/999999")

    assert response.status_code == 404


def test_create_subject_duplicate_name_conflict(client: TestClient) -> None:
    client.post("/api/v1/subjects/", json={"name": "重複科目"})

    response = client.post("/api/v1/subjects/", json={"name": "重複科目"})

    assert response.status_code == 409


# --- Task 49: deleting a Subject must also clear its own TeacherSubject
# rows (owned join-entity, no independent meaning once the subject is
# gone), but still be blocked by a REAL dependent record
# (ClassSubjectRequirement.subject_id) -- and when blocked, no teacher's
# qualifications must be left half-deleted. Same reasoning as Task 48's
# delete_teacher(). ---


def _create_teacher(client: TestClient, name: str) -> int:
    response = client.post(
        "/api/v1/teachers/",
        json={"name": name, "min_weekly_periods": 10, "max_weekly_periods": 20},
    )
    teacher_id: int = response.json()["id"]
    return teacher_id


def test_delete_subject_with_teacher_qualification_succeeds(
    client: TestClient,
) -> None:
    subject_id = client.post(
        "/api/v1/subjects/", json={"name": "Cleanly Deletable Subject"}
    ).json()["id"]
    teacher_id = _create_teacher(client, "Qualified Teacher 49a")
    add_response = client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )
    assert add_response.status_code == 201

    response = client.delete(f"/api/v1/subjects/{subject_id}")

    assert response.status_code == 204
    # The TeacherSubject row is genuinely gone, not just the subject --
    # the teacher's own qualification list is now empty.
    subjects_response = client.get(f"/api/v1/teachers/{teacher_id}/subjects")
    assert subjects_response.status_code == 200
    assert subjects_response.json() == []
    # The teacher himself is untouched -- only the join row was removed.
    assert client.get(f"/api/v1/teachers/{teacher_id}").status_code == 200


def test_delete_subject_blocked_by_requirement_keeps_qualifications(
    client: TestClient,
) -> None:
    subject_id = client.post(
        "/api/v1/subjects/", json={"name": "Required Subject 49b"}
    ).json()["id"]
    teacher_id = _create_teacher(client, "Qualified Teacher 49b")
    client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )

    academic_year_id = client.post(
        "/api/v1/academic-years/", json={"year": 2102}
    ).json()["id"]
    semester_id = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    ).json()["id"]
    grade_id = client.post(
        "/api/v1/grades/", json={"name": "Grade 49b", "level": 49}
    ).json()["id"]
    class_id = client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": "Class 49b"}
    ).json()["id"]
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 2,
        },
    )

    response = client.delete(f"/api/v1/subjects/{subject_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "此資料仍被其他資料參照，無法刪除"
    # Subject AND every teacher's qualification for it survived -- the
    # transaction was fully rolled back, not partially applied.
    get_response = client.get(f"/api/v1/subjects/{subject_id}")
    assert get_response.status_code == 200
    subjects_response = client.get(f"/api/v1/teachers/{teacher_id}/subjects")
    assert [s["id"] for s in subjects_response.json()] == [subject_id]
