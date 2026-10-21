from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.semester_teacher import SemesterTeacher
from tests.conftest import mark_status_in_db
from tests.test_reassign_teacher import _build_world

# Task 80 / v3: DELETE /api/v1/schedule-versions/{id} -- a record goes with
# everything it owns (its settings: requirements and their lessons,
# teachers, grade slots; and its timetable), and with any working copy
# editing it. The published record cannot be deleted. Other records --
# copies included, which keep only their source's number -- are never
# touched. Test data is written straight to the database.

URL = "/api/v1/schedule-versions"
PUBLISHED_DELETE_MESSAGE = "已發布的排課紀錄無法刪除"


# --- Helpers ---


def _copy(client: TestClient, version_id: int) -> int:
    response = client.post(f"{URL}/{version_id}/copy")
    assert response.status_code == 201, response.json()
    new_id: int = response.json()["id"]
    return new_id


def _delete(client: TestClient, version_id: int) -> Any:
    return client.delete(f"{URL}/{version_id}")


def _owned(db: Session, version_id: int) -> dict[str, int]:
    """How many rows of each kind the record owns."""
    db.expire_all()
    requirement_ids = select(ClassSubjectRequirement.id).where(
        ClassSubjectRequirement.schedule_version_id == version_id
    )
    return {
        "requirements": len(db.scalars(requirement_ids).all()),
        "lessons": len(
            db.scalars(
                select(Lesson.id).where(Lesson.class_subject_requirement_id.in_(requirement_ids))
            ).all()
        ),
        "teachers": len(
            db.scalars(
                select(SemesterTeacher.id).where(SemesterTeacher.schedule_version_id == version_id)
            ).all()
        ),
        "schedules": len(
            db.scalars(select(Schedule.id).where(Schedule.schedule_version_id == version_id)).all()
        ),
    }


def _version_exists(db: Session, version_id: int) -> bool:
    db.expire_all()
    return db.get(ScheduleVersion, version_id) is not None


def _snapshot(db: Session) -> list[tuple[object, ...]]:
    """Every column of every version, requirement, Lesson and Schedule row."""
    db.expire_all()
    snapshot: list[tuple[object, ...]] = []
    for model in (ScheduleVersion, ClassSubjectRequirement, Lesson, Schedule):
        columns = list(model.__table__.columns.keys())
        for row in db.scalars(select(model).order_by(model.id)).all():
            snapshot.append((model.__name__, *(getattr(row, c) for c in columns)))
    return snapshot


# --- What a delete takes with it ---


@pytest.mark.parametrize("status", ["AUTO", "MANUAL", "COPIED"])
def test_delete_removes_the_record_and_everything_it_owns(
    client: TestClient, db_session: Session, status: str
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, status)
    assert _owned(db_session, world.version.id) == {
        "requirements": 2,
        "lessons": 3,
        "teachers": 2,
        "schedules": 3,
    }

    response = _delete(client, world.version.id)

    assert response.status_code == 204
    assert not _version_exists(db_session, world.version.id)
    assert _owned(db_session, world.version.id) == {
        "requirements": 0,
        "lessons": 0,
        "teachers": 0,
        "schedules": 0,
    }


def test_delete_leaves_other_records_alone(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO")
    copy_id = _copy(client, world.version.id)
    copy_before = _owned(db_session, copy_id)

    assert _delete(client, world.version.id).status_code == 204

    # The copy keeps everything -- its own settings and timetable -- and
    # still works.
    assert _owned(db_session, copy_id) == copy_before
    assert client.get(f"{URL}/{copy_id}").json()["copied_from_number"] is not None
    assert client.get(f"{URL}/{copy_id}/check").status_code == 200
    assert _copy(client, copy_id) > copy_id


def test_delete_a_working_copy_discards_the_edit_only(
    client: TestClient, db_session: Session
) -> None:
    """Leaving a manual edit without saving deletes its working copy."""
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "MANUAL")
    record_before = _owned(db_session, world.version.id)
    working_copy = client.post(f"{URL}/{world.version.id}/edit").json()

    assert _delete(client, working_copy["id"]).status_code == 204

    assert not _version_exists(db_session, working_copy["id"])
    assert _owned(db_session, world.version.id) == record_before
    assert client.get(f"{URL}/{world.version.id}").json()["status"] == "MANUAL"


def test_delete_not_scheduled_record(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "NOT_SCHEDULED")

    assert _delete(client, world.version.id).status_code == 204
    assert not _version_exists(db_session, world.version.id)


# --- Published ---


def test_delete_published_record_returns_409_and_changes_nothing(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO", is_published=True)
    before = _snapshot(db_session)

    response = _delete(client, world.version.id)

    assert response.status_code == 409
    assert response.json()["detail"] == PUBLISHED_DELETE_MESSAGE
    assert _snapshot(db_session) == before


def test_a_record_that_is_no_longer_published_can_be_deleted(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO", is_published=True)
    replacement = world.builder.version(status="AUTO")
    assert client.post(f"{URL}/{replacement.id}/publish").status_code == 200

    assert _delete(client, world.version.id).status_code == 204


# --- Permissions / not found ---


def test_teacher_cannot_delete_any_record(
    teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    published = world.builder.version(status="AUTO")
    mark_status_in_db(db_session, published.id, "AUTO", is_published=True)

    for version_id in (world.version.id, published.id):
        response = teacher_client.delete(f"{URL}/{version_id}")
        assert response.status_code == 403
        assert _version_exists(db_session, version_id)


def test_delete_missing_record_returns_404(client: TestClient) -> None:
    response = _delete(client, 999_999)

    assert response.status_code == 404
