from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schedule_version import ScheduleVersion
from app.services import schedule_version as schedule_version_service
from tests.conftest import get_test_school_id, mark_status_in_db
from tests.test_reassign_teacher import Builder, _build_world, _rows_of

# v3 (items 8 and 14): 發布此課表 makes a record the semester's one published
# record -- is_published, at most one per semester. The record keeps its
# own status (自動排課 / 手動排課 / 複製自編號 x), and the one published before
# it simply stops being published. Only a record with a timetable can be
# published. Test data is written straight to the database.

NO_TIMETABLE_MESSAGE = "這筆排課紀錄還沒有課表，無法發布"


# --- Helpers ---


def _publish_response(client: TestClient, version_id: int) -> Any:
    return client.post(f"/api/v1/schedule-versions/{version_id}/publish")


def _publish(client: TestClient, version_id: int) -> dict:
    response = _publish_response(client, version_id)
    assert response.status_code == 200, response.json()
    data: dict = response.json()
    assert data["is_published"] is True
    return data


def _states(db: Session, *versions: ScheduleVersion) -> list[tuple[str, bool]]:
    db.expire_all()
    result: list[tuple[str, bool]] = []
    for version in versions:
        row = db.get(ScheduleVersion, version.id)
        assert row is not None
        result.append((row.status, row.is_published))
    return result


def _version_snapshot(db: Session) -> list[tuple[object, ...]]:
    db.expire_all()
    columns = list(ScheduleVersion.__table__.columns.keys())
    return [
        tuple(getattr(row, c) for c in columns)
        for row in db.scalars(select(ScheduleVersion).order_by(ScheduleVersion.id)).all()
    ]


def _records(builder: Builder, *statuses: str) -> list[ScheduleVersion]:
    return [builder.version(status=status) for status in statuses]


# --- Publishing switches the semester's published record ---


def test_publish_with_nothing_published_keeps_the_status(
    client: TestClient, db_session: Session
) -> None:
    v1, v2 = _records(Builder(db_session), "AUTO", "MANUAL")

    data = _publish(client, v1.id)

    assert data["status"] == "AUTO"
    assert _states(db_session, v1, v2) == [("AUTO", True), ("MANUAL", False)]


def test_publish_replaces_the_previously_published_record(
    client: TestClient, db_session: Session
) -> None:
    v1, v2 = _records(Builder(db_session), "AUTO", "COPIED")
    _publish(client, v1.id)

    _publish(client, v2.id)

    # The old one goes back to being an ordinary 自動排課 record.
    assert _states(db_session, v1, v2) == [("AUTO", False), ("COPIED", True)]


def test_publish_back_and_forth(client: TestClient, db_session: Session) -> None:
    v1, v2 = _records(Builder(db_session), "MANUAL", "AUTO")

    _publish(client, v1.id)
    _publish(client, v2.id)
    _publish(client, v1.id)

    assert _states(db_session, v1, v2) == [("MANUAL", True), ("AUTO", False)]


def test_publish_does_not_affect_other_semesters(
    client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(status="AUTO")
    other = builder.version(builder.semester_in_year(number=2), status="AUTO")
    _publish(client, other.id)

    _publish(client, v1.id)

    assert _states(db_session, v1, other) == [("AUTO", True), ("AUTO", True)]


def test_publishing_the_published_record_again_changes_nothing(
    client: TestClient, db_session: Session
) -> None:
    (v1,) = _records(Builder(db_session), "AUTO")
    _publish(client, v1.id)
    before = _version_snapshot(db_session)

    _publish(client, v1.id)

    assert _version_snapshot(db_session) == before


@pytest.mark.parametrize("status", ["NOT_SCHEDULED", "EDITING"])
def test_a_record_without_a_timetable_cannot_be_published(
    client: TestClient, db_session: Session, status: str
) -> None:
    (record,) = _records(Builder(db_session), status)
    before = _version_snapshot(db_session)

    response = _publish_response(client, record.id)

    assert response.status_code == 409
    assert response.json()["detail"] == NO_TIMETABLE_MESSAGE
    assert _version_snapshot(db_session) == before


def test_publish_missing_record_returns_404(client: TestClient) -> None:
    assert _publish_response(client, 999999).status_code == 404


def test_failed_publish_rolls_back_the_unpublish(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    v1, v2 = _records(Builder(db_session), "AUTO", "AUTO")
    _publish(client, v1.id)
    before = _version_snapshot(db_session)

    def fail(schedule_version: ScheduleVersion) -> None:
        raise RuntimeError("simulated failure after the old record was unpublished")

    monkeypatch.setattr(schedule_version_service, "_mark_published", fail)

    with pytest.raises(RuntimeError):
        schedule_version_service.publish_schedule_version(
            db_session, v2.id, school_id=get_test_school_id(db_session)
        )

    assert _version_snapshot(db_session) == before
    assert _states(db_session, v1, v2) == [("AUTO", True), ("AUTO", False)]


def test_database_allows_only_one_published_per_semester(db_session: Session) -> None:
    v1, v2 = _records(Builder(db_session), "AUTO", "AUTO")
    mark_status_in_db(db_session, v1.id, "AUTO", is_published=True)

    row = db_session.get(ScheduleVersion, v2.id)
    assert row is not None
    row.is_published = True
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_database_refuses_a_published_record_without_a_timetable(db_session: Session) -> None:
    (record,) = _records(Builder(db_session), "NOT_SCHEDULED")

    row = db_session.get(ScheduleVersion, record.id)
    assert row is not None
    row.is_published = True
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- What a published record still allows ---


def test_published_timetable_cannot_be_changed_directly(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO", is_published=True)
    row = _rows_of(db_session, world.version.id, world.english_requirement.id)[0]

    response = client.patch(
        f"/api/v1/schedules/{row.id}", json={"time_slot_id": world.builder.slots[5].id}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "課表不能直接修改，請先按「手動編輯課表」"


def test_published_record_can_be_copied_and_checked(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO", is_published=True)

    copied = client.post(f"/api/v1/schedule-versions/{world.version.id}/copy")
    check = client.get(f"/api/v1/schedule-versions/{world.version.id}/check")

    assert copied.status_code == 201
    assert copied.json()["is_published"] is False
    assert check.status_code == 200


# --- Who may publish, who sees it ---


def test_teacher_sees_the_newly_published_record_only(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    v1, v2 = _records(Builder(db_session), "AUTO", "MANUAL")
    _publish(client, v1.id)
    _publish(client, v2.id)

    listed = [version["id"] for version in teacher_client.get("/api/v1/schedule-versions/").json()]

    assert listed == [v2.id]
    assert teacher_client.get(f"/api/v1/schedule-versions/{v1.id}").status_code == 404


def test_teacher_cannot_publish(
    teacher_client: TestClient, db_session: Session
) -> None:
    (record,) = _records(Builder(db_session), "AUTO")
    before = _version_snapshot(db_session)

    assert _publish_response(teacher_client, record.id).status_code == 403
    assert _version_snapshot(db_session) == before


def test_unauthenticated_cannot_publish(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    (record,) = _records(Builder(db_session), "AUTO")

    assert _publish_response(unauthenticated_client, record.id).status_code == 401


# --- 取消發布 ---


def _unpublish_response(client: TestClient, version_id: int) -> Any:
    return client.post(f"/api/v1/schedule-versions/{version_id}/unpublish")


def test_unpublish_leaves_the_semester_without_a_published_record(
    client: TestClient, db_session: Session
) -> None:
    v1, v2 = _records(Builder(db_session), "MANUAL", "AUTO")
    _publish(client, v1.id)

    response = _unpublish_response(client, v1.id)

    assert response.status_code == 200, response.json()
    assert response.json()["is_published"] is False
    # Back to an ordinary 手動排課 record; no other record is published instead.
    assert _states(db_session, v1, v2) == [("MANUAL", False), ("AUTO", False)]


def test_unpublish_then_publish_again(client: TestClient, db_session: Session) -> None:
    (record,) = _records(Builder(db_session), "COPIED")
    _publish(client, record.id)
    _unpublish_response(client, record.id)

    _publish(client, record.id)

    assert _states(db_session, record) == [("COPIED", True)]


def test_unpublishing_a_record_that_is_not_published_changes_nothing(
    client: TestClient, db_session: Session
) -> None:
    (record,) = _records(Builder(db_session), "AUTO")
    before = _version_snapshot(db_session)

    response = _unpublish_response(client, record.id)

    assert response.status_code == 200
    assert _version_snapshot(db_session) == before


def test_unpublish_does_not_affect_other_semesters(
    client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(status="AUTO")
    other = builder.version(builder.semester_in_year(number=2), status="AUTO")
    _publish(client, v1.id)
    _publish(client, other.id)

    _unpublish_response(client, v1.id)

    assert _states(db_session, v1, other) == [("AUTO", False), ("AUTO", True)]


def test_teacher_sees_nothing_once_unpublished(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    (record,) = _records(Builder(db_session), "AUTO")
    _publish(client, record.id)

    _unpublish_response(client, record.id)

    assert teacher_client.get("/api/v1/schedule-versions/").json() == []


def test_unpublish_missing_record_returns_404(client: TestClient) -> None:
    assert _unpublish_response(client, 999999).status_code == 404


def test_teacher_cannot_unpublish(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    (record,) = _records(Builder(db_session), "AUTO")
    _publish(client, record.id)
    before = _version_snapshot(db_session)

    assert _unpublish_response(teacher_client, record.id).status_code == 403
    assert _version_snapshot(db_session) == before
