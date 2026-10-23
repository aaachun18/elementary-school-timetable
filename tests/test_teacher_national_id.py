"""帳號管理: two teachers of one school with the same name are told apart by
身分證字號 -- required for the new account when the name is already taken,
and asked for afterwards for the earlier teacher."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.school import School
from app.models.teacher import Teacher
from tests.test_account_roles import REGISTER_URL, _make_school, _teacher_body, _teacher_of

SAME_NAME_URL = "/api/v1/users/same-name-teachers"


def _national_id_url(teacher_id: int) -> str:
    return f"/api/v1/users/teachers/{teacher_id}/national-id"


def _register(client: TestClient, username: str, name: str, **extra: object) -> int:
    response = client.post(REGISTER_URL, json={**_teacher_body(username, name=name), **extra})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_same_name_requires_national_id(coordinator_client: TestClient) -> None:
    _register(coordinator_client, "wang1", "王小明")

    response = coordinator_client.post(REGISTER_URL, json=_teacher_body("wang2", name="王小明"))

    assert response.status_code == 422
    assert "身分證字號" in response.json()["detail"]


def test_rejected_same_name_account_is_not_created(
    coordinator_client: TestClient, db_session: Session
) -> None:
    _register(coordinator_client, "wang1", "王小明")
    coordinator_client.post(REGISTER_URL, json=_teacher_body("wang2", name="王小明"))

    users = coordinator_client.get("/api/v1/users/").json()
    assert "wang2" not in [user["username"] for user in users]


def test_same_name_with_national_id_is_created(
    coordinator_client: TestClient, db_session: Session
) -> None:
    _register(coordinator_client, "wang1", "王小明")

    user_id = _register(
        coordinator_client, "wang2", "王小明", teacher_national_id=" a123456789 "
    )

    teacher = _teacher_of(db_session, user_id)
    assert teacher is not None
    assert teacher.national_id == "A123456789"


def test_different_name_needs_no_national_id(coordinator_client: TestClient) -> None:
    _register(coordinator_client, "wang1", "王小明")
    _register(coordinator_client, "lee1", "李小華")


def test_national_id_format_is_checked(coordinator_client: TestClient) -> None:
    response = coordinator_client.post(
        REGISTER_URL,
        json={**_teacher_body("wang1", name="王小明"), "teacher_national_id": "123"},
    )

    assert response.status_code == 422


def test_same_name_lookup_lists_earlier_teacher(coordinator_client: TestClient) -> None:
    _register(coordinator_client, "wang1", "王小明")

    response = coordinator_client.get(SAME_NAME_URL, params={"name": " 王小明 "})

    assert response.status_code == 200
    rows = response.json()
    assert [(row["username"], row["has_national_id"]) for row in rows] == [("wang1", False)]
    assert "national_id" not in rows[0]


def test_coordinator_lookup_is_own_school_only(
    coordinator_client: TestClient, admin_client: TestClient, db_session: Session
) -> None:
    other = _make_school(db_session, "別的國小")
    admin_client.post(REGISTER_URL, json=_teacher_body("wang9", other.id, name="王小明"))

    response = coordinator_client.get(
        SAME_NAME_URL, params={"name": "王小明", "school_id": other.id}
    )

    assert response.json() == []


def test_admin_lookup_by_school(admin_client: TestClient, account_school: School) -> None:
    admin_client.post(REGISTER_URL, json=_teacher_body("wang1", account_school.id, name="王小明"))

    assert len(admin_client.get(SAME_NAME_URL, params={"name": "王小明"}).json()) == 0
    rows = admin_client.get(
        SAME_NAME_URL, params={"name": "王小明", "school_id": account_school.id}
    ).json()
    assert [row["username"] for row in rows] == ["wang1"]


def test_set_earlier_teachers_national_id(
    coordinator_client: TestClient, db_session: Session
) -> None:
    first_user_id = _register(coordinator_client, "wang1", "王小明")
    _register(coordinator_client, "wang2", "王小明", teacher_national_id="A123456789")
    first = _teacher_of(db_session, first_user_id)
    assert first is not None

    response = coordinator_client.patch(
        _national_id_url(first.id), json={"national_id": "b234567890"}
    )

    assert response.status_code == 200
    assert response.json()["has_national_id"] is True
    db_session.expire_all()
    assert db_session.get(Teacher, first.id).national_id == "B234567890"  # type: ignore[union-attr]


def test_national_id_unique_within_school(
    coordinator_client: TestClient, db_session: Session
) -> None:
    first_user_id = _register(coordinator_client, "wang1", "王小明")
    _register(coordinator_client, "wang2", "王小明", teacher_national_id="A123456789")
    first = _teacher_of(db_session, first_user_id)
    assert first is not None

    response = coordinator_client.patch(
        _national_id_url(first.id), json={"national_id": "A123456789"}
    )

    assert response.status_code == 409


def test_coordinator_cannot_set_other_schools_teacher(
    coordinator_client: TestClient, admin_client: TestClient, db_session: Session
) -> None:
    other = _make_school(db_session, "別的國小")
    response = admin_client.post(REGISTER_URL, json=_teacher_body("wang9", other.id))
    teacher = _teacher_of(db_session, response.json()["id"])
    assert teacher is not None

    response = coordinator_client.patch(
        _national_id_url(teacher.id), json={"national_id": "A123456789"}
    )

    assert response.status_code == 404


def test_teacher_cannot_use_lookup(teacher_client: TestClient) -> None:
    assert teacher_client.get(SAME_NAME_URL, params={"name": "王小明"}).status_code == 403
