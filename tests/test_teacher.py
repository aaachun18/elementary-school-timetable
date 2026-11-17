from fastapi.testclient import TestClient

from tests.api_helpers import create_teacher

# Task 98: a teacher is created (and 停用 / 啟用) with its 一般老師 account;
# /teachers only reads the school's teachers and renames one. Teaching
# qualifications and the teacher-wide unavailable slots / weekly periods
# range are gone (the last two are per semester now: test_semester_settings.py).

URL = "/api/v1/teachers/"


def test_account_creates_a_teacher_listed_here(client: TestClient) -> None:
    teacher_id = create_teacher(client, "王老師")

    data = client.get(f"{URL}{teacher_id}").json()

    assert data["name"] == "王老師"
    assert data["is_active"] is True
    assert data["user_id"] is not None
    assert "min_weekly_periods" not in data
    assert "max_weekly_periods" not in data


def test_list_teachers_in_id_order(client: TestClient) -> None:
    first = create_teacher(client, "甲老師")
    second = create_teacher(client, "乙老師")

    data = client.get(URL).json()

    assert [item["id"] for item in data] == [first, second]


def test_get_teacher_not_found(client: TestClient) -> None:
    assert client.get(f"{URL}999999").status_code == 404


def test_rename_teacher(client: TestClient) -> None:
    teacher_id = create_teacher(client, "舊名字")

    response = client.patch(f"{URL}{teacher_id}", json={"name": "新名字"})

    assert response.status_code == 200
    assert response.json()["name"] == "新名字"


def test_rename_teacher_not_found(client: TestClient) -> None:
    assert client.patch(f"{URL}999999", json={"name": "x"}).status_code == 404


def test_teacher_can_only_be_created_or_deleted_with_its_account(client: TestClient) -> None:
    teacher_id = create_teacher(client, "王老師")

    create = client.post(URL, json={"name": "直接建立"})
    delete = client.delete(f"{URL}{teacher_id}")

    assert create.status_code == 405
    assert delete.status_code == 405


def test_qualification_and_global_unavailability_endpoints_are_gone(client: TestClient) -> None:
    teacher_id = create_teacher(client, "王老師")

    assert client.get(f"{URL}{teacher_id}/subjects").status_code == 404
    assert client.get(f"{URL}{teacher_id}/unavailable-slots").status_code == 404


def test_teacher_account_reads_but_cannot_rename(
    client: TestClient, teacher_client: TestClient
) -> None:
    teacher_id = create_teacher(client, "王老師")

    assert teacher_client.get(f"{URL}{teacher_id}").status_code == 200
    response = teacher_client.patch(f"{URL}{teacher_id}", json={"name": "改名"})

    assert response.status_code == 403


def test_deactivating_the_account_deactivates_the_teacher(
    client: TestClient, admin_client: TestClient
) -> None:
    teacher_id = create_teacher(client, "王老師")
    user_id = client.get(f"{URL}{teacher_id}").json()["user_id"]

    # 帳號改版: 停用 is the 系統管理員's.
    response = admin_client.patch(f"/api/v1/users/{user_id}", json={"is_active": False})
    assert response.status_code == 200

    assert client.get(f"{URL}{teacher_id}").json()["is_active"] is False
