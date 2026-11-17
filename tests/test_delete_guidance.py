"""「此資料仍被其他資料參照，無法刪除」 comes with delete_steps: what to do
first, in order, so the delete succeeds (services/delete_guidance.py)."""

from fastapi.testclient import TestClient

from tests.api_helpers import create_class, create_grade, create_record, mark_status

CSR = "/api/v1/class-subject-requirements/"


def _semester(client: TestClient, year: int = 115) -> int:
    year_id = client.post("/api/v1/academic-years/", json={"year": year}).json()["id"]
    semester_id: int = client.post(
        "/api/v1/semesters/", json={"academic_year_id": year_id, "number": 1}
    ).json()["id"]
    return semester_id


def _requirement(client: TestClient, record_id: int, class_id: int, subject_id: int) -> None:
    response = client.post(
        CSR,
        json={
            "schedule_version_id": record_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 2,
        },
    )
    assert response.status_code == 201, response.text


def test_class_steps_delete_records_oldest_first(client: TestClient) -> None:
    """編號 1 is the newest record and deleting a record renumbers the older
    ones, so the oldest (largest 編號) comes first."""
    semester_id = _semester(client)
    class_id = create_class(client, create_grade(client, level=1), "一年甲班")
    subject_id = client.post("/api/v1/subjects/", json={"name": "國語文"}).json()["id"]
    older = create_record(client, semester_id)
    create_record(client, semester_id)  # not using the class
    newer = create_record(client, semester_id)
    _requirement(client, older, class_id, subject_id)
    _requirement(client, newer, class_id, subject_id)

    response = client.delete(f"/api/v1/classes/{class_id}")

    assert response.status_code == 409
    assert response.json()["delete_steps"] == [
        "到「排課紀錄」刪除排課紀錄編號 3（115 學年度第 1 學期）",
        "到「排課紀錄」刪除排課紀錄編號 1（115 學年度第 1 學期）",
    ]


def test_published_record_must_stop_being_published_first(client: TestClient) -> None:
    semester_id = _semester(client)
    class_id = create_class(client, create_grade(client, level=1), "一年甲班")
    subject_id = client.post("/api/v1/subjects/", json={"name": "國語文"}).json()["id"]
    record_id = create_record(client, semester_id)
    _requirement(client, record_id, class_id, subject_id)
    mark_status(client, record_id, "AUTO", is_published=True)

    response = client.delete(f"/api/v1/classes/{class_id}")

    assert response.json()["delete_steps"] == [
        "排課紀錄編號 1（115 學年度第 1 學期）是目前發布中的課表，請先在排課紀錄發布同學期的另一筆紀錄",
        "到「排課紀錄」刪除排課紀錄編號 1（115 學年度第 1 學期）",
    ]


def test_unreferenced_delete_still_succeeds(client: TestClient) -> None:
    class_id = create_class(client, create_grade(client, level=1), "一年甲班")

    assert client.delete(f"/api/v1/classes/{class_id}").status_code == 204
