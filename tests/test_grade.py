from fastapi.testclient import TestClient

from tests.api_helpers import create_grade


def test_get_grade_list_ordered_by_level(client: TestClient) -> None:
    second = create_grade(client, "二年級")
    first = create_grade(client, "三年級")

    response = client.get("/api/v1/grades/")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [second, first]
    assert [item["level"] for item in data] == sorted(item["level"] for item in data)


def test_get_grade_by_id(client: TestClient) -> None:
    grade_id = create_grade(client, "Get Grade")

    response = client.get(f"/api/v1/grades/{grade_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Get Grade"


def test_get_grade_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/grades/999999")

    assert response.status_code == 404


def test_grades_cannot_be_created_changed_or_deleted(client: TestClient) -> None:
    """A school's grades are built with the school from its type."""
    grade_id = create_grade(client)

    assert client.post("/api/v1/grades/", json={"name": "一年級", "level": 1}).status_code == 405
    assert client.patch(f"/api/v1/grades/{grade_id}", json={"name": "x"}).status_code == 405
    assert client.delete(f"/api/v1/grades/{grade_id}").status_code == 405
