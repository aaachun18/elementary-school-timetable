from fastapi.testclient import TestClient
from tests.api_helpers import create_class, create_grade, create_record


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
    assert response.json()["detail"] == "科目名稱重複，這所學校已經有同名的科目"


# --- Task 49 (Task 98: teaching qualifications are gone, so there is no
# join row to clean up any more): a subject a requirement still needs can't
# be deleted. ---


def test_delete_subject_blocked_by_requirement(client: TestClient) -> None:
    subject_id = client.post(
        "/api/v1/subjects/", json={"name": "Required Subject 49b"}
    ).json()["id"]
    academic_year_id = client.post(
        "/api/v1/academic-years/", json={"year": 2102}
    ).json()["id"]
    semester_id = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    ).json()["id"]
    grade_id = create_grade(client, "Grade 49b")
    class_id = create_class(client, grade_id, "Class 49b")
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": create_record(client, semester_id),
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 2,
        },
    )

    response = client.delete(f"/api/v1/subjects/{subject_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "此資料仍被其他資料參照，無法刪除"
    # What to delete first, shown behind the error's ? icon.
    assert response.json()["delete_steps"] == [
        "到「排課紀錄」刪除排課紀錄編號 1（2102 學年度第 1 學期）"
    ]
    assert client.get(f"/api/v1/subjects/{subject_id}").status_code == 200


def test_delete_subject_blocked_by_grade_requirement_says_which_grades(
    client: TestClient,
) -> None:
    subject_id = client.post("/api/v1/subjects/", json={"name": "書法"}).json()["id"]
    for level, name in ((2, "二年級"), (1, "一年級")):
        grade_id = create_grade(client, name, level=level)
        created = client.post(
            "/api/v1/grade-subject-requirements/",
            json={"grade_id": grade_id, "subject_id": subject_id, "weekly_periods": 1},
        )
        assert created.status_code == 201, created.text

    response = client.delete(f"/api/v1/subjects/{subject_id}")

    assert response.status_code == 409
    assert response.json()["delete_steps"] == [
        "到「學校資料 > 科目需求」刪除一年級、二年級的這個科目"
    ]
