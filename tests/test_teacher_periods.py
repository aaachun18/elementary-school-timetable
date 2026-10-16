"""Task 88: a teacher's weekly periods range -- min_weekly_periods may not
be above max_weekly_periods and neither may be negative, on create and on
update (422, Chinese message)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services.teacher_periods import (
    NEGATIVE_MAX_MESSAGE,
    NEGATIVE_MIN_MESSAGE,
    RANGE_MESSAGE,
)

URL = "/api/v1/teachers/"


def _messages(response: Any) -> str:
    """Every message in a 422 body: the plain string of a service error,
    or the msg of each item of a request validation error."""
    detail = response.json()["detail"]
    if isinstance(detail, str):
        return detail
    return " ".join(item["msg"] for item in detail)


def _create(client: TestClient, minimum: int, maximum: int) -> Any:
    return client.post(
        URL,
        json={"name": "老師", "min_weekly_periods": minimum, "max_weekly_periods": maximum},
    )


@pytest.mark.parametrize(
    ("minimum", "maximum", "message"),
    [
        (20, 15, RANGE_MESSAGE),
        (-1, 10, NEGATIVE_MIN_MESSAGE),
        (0, -1, NEGATIVE_MAX_MESSAGE),
    ],
)
def test_create_rejects_bad_ranges_with_422(
    client: TestClient, minimum: int, maximum: int, message: str
) -> None:
    response = _create(client, minimum, maximum)

    assert response.status_code == 422
    assert message in _messages(response)
    assert client.get(URL).json() == []


@pytest.mark.parametrize(("minimum", "maximum"), [(0, 0), (10, 10), (0, 20)])
def test_create_accepts_valid_ranges(client: TestClient, minimum: int, maximum: int) -> None:
    response = _create(client, minimum, maximum)

    assert response.status_code == 201, response.json()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"min_weekly_periods": 21}, RANGE_MESSAGE),  # above the stored max (20)
        ({"max_weekly_periods": 9}, RANGE_MESSAGE),  # below the stored min (10)
        ({"min_weekly_periods": 15, "max_weekly_periods": 12}, RANGE_MESSAGE),
        ({"min_weekly_periods": -1}, NEGATIVE_MIN_MESSAGE),
        ({"max_weekly_periods": -5}, NEGATIVE_MAX_MESSAGE),
    ],
)
def test_update_rejects_bad_ranges_with_422(
    client: TestClient, body: dict[str, int], message: str
) -> None:
    teacher_id = _create(client, 10, 20).json()["id"]

    response = client.patch(f"{URL}{teacher_id}", json=body)

    assert response.status_code == 422
    assert message in _messages(response)
    stored = client.get(f"{URL}{teacher_id}").json()
    assert (stored["min_weekly_periods"], stored["max_weekly_periods"]) == (10, 20)


def test_update_checks_the_values_it_leaves_behind(client: TestClient) -> None:
    teacher_id = _create(client, 10, 20).json()["id"]

    # Raising both together is fine even though the new min is above the
    # old max.
    response = client.patch(
        f"{URL}{teacher_id}", json={"min_weekly_periods": 25, "max_weekly_periods": 30}
    )
    renamed = client.patch(f"{URL}{teacher_id}", json={"name": "新名字"})

    assert response.status_code == 200, response.json()
    assert renamed.status_code == 200, renamed.json()
    assert (renamed.json()["min_weekly_periods"], renamed.json()["max_weekly_periods"]) == (25, 30)
