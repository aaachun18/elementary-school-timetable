from fastapi.testclient import TestClient

from tests.api_helpers import create_grade


def _post_class(client: TestClient, grade_id: int, name: str, name_style: str = "HEAVENLY_STEM"):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/classes/",
        json={"grade_id": grade_id, "name_style": name_style, "name": name},
    )


def test_create_class(client: TestClient) -> None:
    grade_id = create_grade(client, "一年級", level=1)

    response = _post_class(client, grade_id, "一年甲班")

    assert response.status_code == 201
    data = response.json()
    assert data["grade_id"] == grade_id
    assert data["name"] == "一年甲班"
    assert data["name_style"] == "HEAVENLY_STEM"
    assert "is_active" not in data
    assert "homeroom_room_id" not in data
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_class_with_each_name_style(client: TestClient) -> None:
    grade_id = create_grade(client, "三年級", level=3)

    assert _post_class(client, grade_id, "三年三十班", "NUMBER").status_code == 201
    assert _post_class(client, grade_id, "三年癸班", "HEAVENLY_STEM").status_code == 201
    assert _post_class(client, grade_id, "三年平班", "VIRTUE").status_code == 201


def test_create_class_names_senior_high_grades_from_one(client: TestClient) -> None:
    """高中 levels 10-12 are 一到三年級: level 10's classes are 一年…班."""
    grade_id = create_grade(client, "一年級", level=10)

    assert _post_class(client, grade_id, "一年甲班").status_code == 201
    assert _post_class(client, grade_id, "十年甲班").status_code == 422


def test_create_class_name_must_be_an_option_of_its_grade_and_style(
    client: TestClient,
) -> None:
    grade_id = create_grade(client, "二年級", level=2)

    for name, style in (
        ("一年甲班", "HEAVENLY_STEM"),  # another grade's name
        ("二年一班", "HEAVENLY_STEM"),  # another style's name
        ("二年子班", "HEAVENLY_STEM"),  # beyond 癸
        ("二年三十一班", "NUMBER"),  # beyond 三十
        ("二年甲", "HEAVENLY_STEM"),
    ):
        response = _post_class(client, grade_id, name, style)
        assert response.status_code == 422, name
        assert response.json()["detail"] == "班級名稱必須是該年級與名稱類型提供的選項"


def test_create_class_unknown_name_style_is_422(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)

    assert _post_class(client, grade_id, "一年甲班", "LETTER").status_code == 422


def test_create_class_duplicate_name_in_grade_is_409(client: TestClient) -> None:
    grade_id = create_grade(client, "四年級", level=4)
    assert _post_class(client, grade_id, "四年甲班").status_code == 201

    response = _post_class(client, grade_id, "四年甲班")

    assert response.status_code == 409


def test_get_class_list_filters_by_grade(client: TestClient) -> None:
    first = create_grade(client, "五年級", level=5)
    second = create_grade(client, "六年級", level=6)
    _post_class(client, first, "五年甲班")
    _post_class(client, second, "六年甲班")

    everything = client.get("/api/v1/classes/").json()
    only_second = client.get("/api/v1/classes/", params={"grade_id": second}).json()

    assert {item["name"] for item in everything} == {"五年甲班", "六年甲班"}
    assert [item["name"] for item in only_second] == ["六年甲班"]


def test_get_class_by_id(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    class_id = _post_class(client, grade_id, "一年乙班").json()["id"]

    response = client.get(f"/api/v1/classes/{class_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "一年乙班"


def test_get_class_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/classes/999999")

    assert response.status_code == 404


def test_class_cannot_be_edited(client: TestClient) -> None:
    """A class is only created and deleted."""
    grade_id = create_grade(client, level=1)
    class_id = _post_class(client, grade_id, "一年丙班").json()["id"]

    response = client.patch(f"/api/v1/classes/{class_id}", json={"name": "一年丁班"})

    assert response.status_code == 405


def test_delete_class(client: TestClient) -> None:
    grade_id = create_grade(client, level=6)
    class_id = _post_class(client, grade_id, "六年乙班").json()["id"]

    response = client.delete(f"/api/v1/classes/{class_id}")

    assert response.status_code == 204
    assert client.get(f"/api/v1/classes/{class_id}").status_code == 404


def test_delete_class_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/classes/999999")

    assert response.status_code == 404


def test_create_class_invalid_grade_id(client: TestClient) -> None:
    response = _post_class(client, 999999, "一年甲班")

    assert response.status_code == 422
