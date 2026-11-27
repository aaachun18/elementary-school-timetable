from fastapi.testclient import TestClient

from tests.test_scheduler import _create_record

# Task 103: ScheduleVersion.wizard_furthest_step -- the furthest 開始排課
# step a record has reached. PATCH /schedule-versions/{id} sets it, and it
# only ever goes up.

URL = "/api/v1/schedule-versions"


def test_a_new_record_has_none(client: TestClient) -> None:
    record_id = _create_record(client, 10311)

    assert client.get(f"{URL}/{record_id}").json()["wizard_furthest_step"] is None


def test_it_only_goes_up(client: TestClient) -> None:
    record_id = _create_record(client, 10312)

    first = client.patch(f"{URL}/{record_id}", json={"wizard_furthest_step": 3})
    lower = client.patch(f"{URL}/{record_id}", json={"wizard_furthest_step": 1})
    higher = client.patch(f"{URL}/{record_id}", json={"wizard_furthest_step": 5})

    assert first.status_code == 200
    assert first.json()["wizard_furthest_step"] == 3
    assert lower.json()["wizard_furthest_step"] == 3
    assert higher.json()["wizard_furthest_step"] == 5


def test_a_note_alone_leaves_it_as_it_is(client: TestClient) -> None:
    record_id = _create_record(client, 10313)
    client.patch(f"{URL}/{record_id}", json={"wizard_furthest_step": 2})

    response = client.patch(f"{URL}/{record_id}", json={"note": "備註"})

    assert response.json()["wizard_furthest_step"] == 2
    assert response.json()["note"] == "備註"


def test_it_leaves_the_note_as_it_is(client: TestClient) -> None:
    record_id = _create_record(client, 10314)
    client.patch(f"{URL}/{record_id}", json={"note": "備註"})

    response = client.patch(f"{URL}/{record_id}", json={"wizard_furthest_step": 2})

    assert response.json()["note"] == "備註"


def test_a_negative_step_is_refused(client: TestClient) -> None:
    record_id = _create_record(client, 10315)

    assert client.patch(f"{URL}/{record_id}", json={"wizard_furthest_step": -1}).status_code == 422


def test_a_teacher_cannot_set_it(client: TestClient, teacher_client: TestClient) -> None:
    record_id = _create_record(client, 10316)

    response = teacher_client.patch(f"{URL}/{record_id}", json={"wizard_furthest_step": 2})

    assert response.status_code == 403
