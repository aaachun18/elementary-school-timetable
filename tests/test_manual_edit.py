from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from tests.conftest import mark_status_in_db
from tests.test_reassign_teacher import World, _build_world

# v3 (item 10): 手動編輯課表 starts a working copy (EDITING) of a record;
# 儲存課表 saves it -- over an unpublished 手動排課 record, as a new 手動排課
# record for anything else -- and deleting the working copy throws the edit
# away. Test data is written straight to the database.

URL = "/api/v1/schedule-versions"


def _edit(client: TestClient, version_id: int) -> dict:
    response = client.post(f"{URL}/{version_id}/edit")
    assert response.status_code == 201, response.json()
    data: dict = response.json()
    return data


def _save(client: TestClient, working_copy_id: int) -> Any:
    return client.post(f"{URL}/{working_copy_id}/save")


def _slots(db: Session, version_id: int) -> list[int | None]:
    """The record's timetable, as the time slots of its rows by (class,
    subject, sequence) -- comparable across copies, whose ids differ."""
    db.expire_all()
    rows = db.execute(
        select(Schedule.time_slot_id)
        .join(Lesson, Schedule.lesson_id == Lesson.id)
        .join(ClassSubjectRequirement, Lesson.class_subject_requirement_id == ClassSubjectRequirement.id)
        .where(Schedule.schedule_version_id == version_id)
        .order_by(
            ClassSubjectRequirement.class_id,
            ClassSubjectRequirement.subject_id,
            Lesson.sequence_number,
        )
    ).all()
    return [row[0] for row in rows]


def _first_row(db: Session, version_id: int) -> Schedule:
    db.expire_all()
    return db.scalars(
        select(Schedule).where(Schedule.schedule_version_id == version_id).order_by(Schedule.id)
    ).first()  # type: ignore[return-value]


def _move_first_row(client: TestClient, db: Session, working_copy_id: int, world: World) -> int:
    row = _first_row(db, working_copy_id)
    target = world.builder.slots[5].id
    response = client.post(
        f"{URL}/{working_copy_id}/move-lesson",
        json={"schedule_id": row.id, "target_time_slot_id": target},
    )
    assert response.status_code == 200, response.json()
    return target


def _record(db: Session, version_id: int) -> ScheduleVersion | None:
    db.expire_all()
    return db.get(ScheduleVersion, version_id)


# --- 手動編輯課表 ---


def test_edit_makes_a_working_copy_of_settings_and_timetable(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO")

    working_copy = _edit(client, world.version.id)

    assert working_copy["status"] == "EDITING"
    assert working_copy["version_number"] is None
    assert working_copy["editing_source_id"] == world.version.id
    assert _slots(db_session, working_copy["id"]) == _slots(db_session, world.version.id)
    requirements = client.get(
        "/api/v1/class-subject-requirements/", params={"schedule_version_id": working_copy["id"]}
    ).json()
    assert len(requirements) == 2


@pytest.mark.parametrize("status", ["NOT_SCHEDULED", "EDITING"])
def test_a_record_without_a_timetable_cannot_be_edited(
    client: TestClient, db_session: Session, status: str
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, status)

    response = client.post(f"{URL}/{world.version.id}/edit")

    assert response.status_code == 409
    assert response.json()["detail"] == "這筆排課紀錄還沒有課表，無法手動編輯"


def test_a_new_edit_replaces_an_unsaved_one(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO")
    first = _edit(client, world.version.id)

    second = _edit(client, world.version.id)

    assert _record(db_session, first["id"]) is None
    assert _record(db_session, second["id"]) is not None


def test_editing_never_changes_the_record_itself(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO")
    before = _slots(db_session, world.version.id)
    working_copy = _edit(client, world.version.id)

    _move_first_row(client, db_session, working_copy["id"], world)

    assert _slots(db_session, world.version.id) == before
    assert _slots(db_session, working_copy["id"]) != before


# --- 儲存課表 ---


@pytest.mark.parametrize(("status", "is_published"), [("AUTO", False), ("COPIED", False), ("MANUAL", True)])
def test_saving_makes_a_new_manual_record(
    client: TestClient, db_session: Session, status: str, is_published: bool
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, status, is_published=is_published)
    source_number = _record(db_session, world.version.id).version_number  # type: ignore[union-attr]
    before = _slots(db_session, world.version.id)
    working_copy = _edit(client, world.version.id)
    _move_first_row(client, db_session, working_copy["id"], world)
    edited = _slots(db_session, working_copy["id"])

    response = _save(client, working_copy["id"])

    assert response.status_code == 200, response.json()
    saved = response.json()
    assert saved["id"] == working_copy["id"]
    assert saved["status"] == "MANUAL"
    assert saved["version_number"] > source_number
    assert saved["editing_source_id"] is None
    assert saved["is_published"] is False
    assert _slots(db_session, saved["id"]) == edited
    # The record it came from is exactly as it was.
    source = _record(db_session, world.version.id)
    assert source is not None
    assert (source.status, source.is_published) == (status, is_published)
    assert _slots(db_session, world.version.id) == before
    assert world.version.id in [v["id"] for v in client.get(f"{URL}/").json()]


def test_saving_an_unpublished_manual_record_saves_over_it(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "MANUAL")
    record = _record(db_session, world.version.id)
    assert record is not None
    number, created_at = record.version_number, record.created_at
    working_copy = _edit(client, world.version.id)
    _move_first_row(client, db_session, working_copy["id"], world)
    edited = _slots(db_session, working_copy["id"])

    response = _save(client, working_copy["id"])

    assert response.status_code == 200, response.json()
    saved = response.json()
    assert saved["id"] == world.version.id
    assert (saved["status"], saved["version_number"]) == ("MANUAL", number)
    assert _record(db_session, world.version.id).created_at == created_at  # type: ignore[union-attr]
    assert _slots(db_session, world.version.id) == edited
    # The working copy is gone; the record owns the edited settings now.
    assert _record(db_session, working_copy["id"]) is None
    requirements = client.get(
        "/api/v1/class-subject-requirements/", params={"schedule_version_id": world.version.id}
    ).json()
    assert len(requirements) == 2


def test_only_a_working_copy_can_be_saved(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO")

    response = _save(client, world.version.id)

    assert response.status_code == 409
    assert response.json()["detail"] == "這不是編輯中的課表，無法儲存"


def test_save_missing_record_returns_404(client: TestClient) -> None:
    assert _save(client, 999999).status_code == 404


# --- 取消編輯 ---


def test_deleting_the_working_copy_throws_the_edit_away(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO")
    before = _slots(db_session, world.version.id)
    working_copy = _edit(client, world.version.id)
    _move_first_row(client, db_session, working_copy["id"], world)

    assert client.delete(f"{URL}/{working_copy['id']}").status_code == 204

    assert _record(db_session, working_copy["id"]) is None
    assert _slots(db_session, world.version.id) == before
    assert _record(db_session, world.version.id).status == "AUTO"  # type: ignore[union-attr]


# --- Permissions ---


def test_teacher_cannot_edit_or_save(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO", is_published=True)
    working_copy = _edit(client, world.version.id)

    assert teacher_client.post(f"{URL}/{world.version.id}/edit").status_code == 403
    assert teacher_client.post(f"{URL}/{working_copy['id']}/save").status_code == 403
