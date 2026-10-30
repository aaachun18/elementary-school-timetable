"""帳號管理's 搜尋帳號: GET /api/v1/users/?search=... keeps the accounts whose
帳號名稱, 教師姓名 or 身分證字號 contains the text (ignoring case). The number
is searched by the backend because the list only carries it masked."""

from fastapi.testclient import TestClient

from tests.test_teacher_national_id import _register

URL = "/api/v1/users/"


def _usernames(client: TestClient, search: str | None) -> list[str]:
    params = {} if search is None else {"search": search}
    response = client.get(URL, params=params)
    assert response.status_code == 200, response.text
    return [user["username"] for user in response.json()]


def _three_teachers(client: TestClient) -> None:
    _register(client, "wang1", "王小明")
    _register(client, "wang2", "王小明", teacher_national_id="A123456789")
    _register(client, "chen", "陳美玲")


def test_search_by_account_name_name_or_national_id(coordinator_client: TestClient) -> None:
    _three_teachers(coordinator_client)

    assert _usernames(coordinator_client, "WANG") == ["wang1", "wang2"]
    assert _usernames(coordinator_client, "美玲") == ["chen"]
    assert _usernames(coordinator_client, "a1234") == ["wang2"]


def test_no_or_blank_search_lists_every_account(coordinator_client: TestClient) -> None:
    _three_teachers(coordinator_client)

    assert _usernames(coordinator_client, None) == ["wang1", "wang2", "chen"]
    assert _usernames(coordinator_client, "  ") == ["wang1", "wang2", "chen"]


def test_search_matches_nothing(coordinator_client: TestClient) -> None:
    _three_teachers(coordinator_client)

    assert _usernames(coordinator_client, "李") == []


def test_percent_and_underscore_are_plain_characters(coordinator_client: TestClient) -> None:
    _three_teachers(coordinator_client)

    assert _usernames(coordinator_client, "%") == []
    assert _usernames(coordinator_client, "_") == []
