from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.schemas.schedule_version import ScheduleVersionUpdate
from app.services import schedule_version as schedule_version_service
from tests.test_reassign_teacher import Builder, World, _build_world, _rows_of

# Task 64: publishing switches the semester's live version -- exactly one
# PUBLISHED per semester, the replaced one becomes ARCHIVED (and can be
# published again); PUBLISHED and ARCHIVED are both fully locked. Test data
# is written straight to the database through db_session.

ARCHIVED_LOCKED_MESSAGE = "已封存的課表無法修改，請先複製成新草稿"
INVALID_TRANSITION_MESSAGE = "不允許的課表狀態變更"


# --- Helpers ---


def _patch(client: TestClient, version_id: int, body: dict[str, Any]) -> Any:
    return client.patch(f"/api/v1/schedule-versions/{version_id}", json=body)


def _publish(client: TestClient, version_id: int) -> None:
    response = _patch(client, version_id, {"status": "PUBLISHED"})
    assert response.status_code == 200, response.json()
    assert response.json()["status"] == "PUBLISHED"


def _statuses(db: Session, *versions: ScheduleVersion) -> list[str]:
    db.expire_all()
    result: list[str] = []
    for version in versions:
        row = db.get(ScheduleVersion, version.id)
        assert row is not None
        result.append(row.status)
    return result


def _published_count(db: Session, semester_id: int) -> int:
    db.expire_all()
    return len(
        db.scalars(
            select(ScheduleVersion).where(
                ScheduleVersion.semester_id == semester_id,
                ScheduleVersion.status == "PUBLISHED",
            )
        ).all()
    )


def _version_snapshot(db: Session) -> list[tuple[object, ...]]:
    db.expire_all()
    columns = list(ScheduleVersion.__table__.columns.keys())
    return [
        tuple(getattr(row, c) for c in columns)
        for row in db.scalars(select(ScheduleVersion).order_by(ScheduleVersion.id)).all()
    ]


def _full_snapshot(db: Session) -> list[tuple[object, ...]]:
    """Every column of every version, requirement, Lesson and Schedule row."""
    db.expire_all()
    snapshot: list[tuple[object, ...]] = []
    for model in (ScheduleVersion, ClassSubjectRequirement, Lesson, Schedule):
        columns = list(model.__table__.columns.keys())
        for row in db.scalars(select(model).order_by(model.id)).all():
            snapshot.append((model.__name__, *(getattr(row, c) for c in columns)))
    return snapshot


def _archived_world(client: TestClient, db: Session) -> tuple[World, ScheduleVersion]:
    """_build_world()'s version (v1, with Schedule rows) published and then
    replaced by publishing v2 -- so v1 is ARCHIVED the normal way. Returns
    (world, v2)."""
    world = _build_world(db)
    v2 = world.builder.version(number=2)
    _publish(client, world.version.id)
    _publish(client, v2.id)
    assert _statuses(db, world.version, v2) == ["ARCHIVED", "PUBLISHED"]
    return world, v2


# --- Publishing switches the live version ---


def test_publish_with_no_published_version_archives_nothing(
    client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)

    _publish(client, v1.id)

    assert _statuses(db_session, v1, v2) == ["PUBLISHED", "DRAFT"]


def test_publish_archives_previous_published_version(
    client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)
    _publish(client, v1.id)

    _publish(client, v2.id)

    assert _statuses(db_session, v1, v2) == ["ARCHIVED", "PUBLISHED"]


def test_publish_back_and_forth(client: TestClient, db_session: Session) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)
    v3 = builder.version(number=3)  # stays DRAFT throughout
    semester_id = builder.semester.id

    expected_after_each_step = [
        (v1, ["PUBLISHED", "DRAFT", "DRAFT"]),
        (v2, ["ARCHIVED", "PUBLISHED", "DRAFT"]),
        (v1, ["PUBLISHED", "ARCHIVED", "DRAFT"]),
        (v2, ["ARCHIVED", "PUBLISHED", "DRAFT"]),
    ]
    for version, expected in expected_after_each_step:
        _publish(client, version.id)
        assert _published_count(db_session, semester_id) == 1
        assert _statuses(db_session, v1, v2, v3) == expected


def test_publish_does_not_affect_other_semesters(
    client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    other_semester = builder.semester_in_year(number=2)
    other_published = builder.version(other_semester, number=1)
    _publish(client, other_published.id)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)

    _publish(client, v1.id)
    _publish(client, v2.id)

    assert _statuses(db_session, other_published) == ["PUBLISHED"]
    assert _published_count(db_session, other_semester.id) == 1


def test_publish_does_not_affect_other_drafts(
    client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)
    other_draft = builder.version(number=3)
    _publish(client, v1.id)
    draft_before = [row for row in _version_snapshot(db_session) if row[0] == other_draft.id]

    _publish(client, v2.id)

    assert [
        row for row in _version_snapshot(db_session) if row[0] == other_draft.id
    ] == draft_before


def test_unchanged_status_is_a_no_op(client: TestClient, db_session: Session) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)
    _publish(client, v1.id)
    _publish(client, v2.id)
    before = _version_snapshot(db_session)

    for version, status in ((v2, "PUBLISHED"), (v1, "ARCHIVED")):
        response = _patch(client, version.id, {"status": status})
        assert response.status_code == 200
        assert response.json()["status"] == status

    assert _version_snapshot(db_session) == before


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        ("PUBLISHED", "DRAFT"),
        ("ARCHIVED", "DRAFT"),
        ("DRAFT", "ARCHIVED"),
        # PUBLISHED -> ARCHIVED became "unpublish" in Task 65.
    ],
)
def test_invalid_status_transition_returns_409(
    client: TestClient, db_session: Session, from_status: str, to_status: str
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)
    v3 = builder.version(number=3)
    _publish(client, v1.id)
    _publish(client, v2.id)  # v1 ARCHIVED, v2 PUBLISHED, v3 DRAFT
    target = {"ARCHIVED": v1, "PUBLISHED": v2, "DRAFT": v3}[from_status]
    before = _version_snapshot(db_session)

    response = _patch(client, target.id, {"status": to_status})

    assert response.status_code == 409
    assert response.json()["detail"] == INVALID_TRANSITION_MESSAGE
    assert _version_snapshot(db_session) == before


# --- Task 65: unpublish (PUBLISHED -> ARCHIVED) ---


def test_unpublish_leaves_semester_without_published_version(
    client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)
    _publish(client, v1.id)

    response = _patch(client, v1.id, {"status": "ARCHIVED"})

    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"
    assert _statuses(db_session, v1, v2) == ["ARCHIVED", "DRAFT"]
    assert _published_count(db_session, builder.semester.id) == 0


def test_after_unpublish_teacher_sees_no_version(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    _publish(client, v1.id)
    _patch(client, v1.id, {"status": "ARCHIVED"})

    teacher_versions = teacher_client.get("/api/v1/schedule-versions/").json()
    admin_versions = client.get("/api/v1/schedule-versions/").json()

    assert teacher_versions == []
    assert [v["id"] for v in admin_versions] == [v1.id]


@pytest.mark.parametrize("republish", ["archived", "draft"])
def test_after_unpublish_any_version_can_be_published(
    client: TestClient, db_session: Session, republish: str
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)
    _publish(client, v1.id)
    _patch(client, v1.id, {"status": "ARCHIVED"})

    _publish(client, v1.id if republish == "archived" else v2.id)

    assert _published_count(db_session, builder.semester.id) == 1
    expected = ["PUBLISHED", "DRAFT"] if republish == "archived" else ["ARCHIVED", "PUBLISHED"]
    assert _statuses(db_session, v1, v2) == expected


def test_unpublished_version_stays_locked(client: TestClient, db_session: Session) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    _publish(client, v1.id)
    _patch(client, v1.id, {"status": "ARCHIVED"})
    before = _version_snapshot(db_session)

    edit = _patch(client, v1.id, {"version_number": 9})
    delete = client.delete(f"/api/v1/schedule-versions/{v1.id}")
    back_to_draft = _patch(client, v1.id, {"status": "DRAFT"})

    _assert_archived_lock(edit)
    _assert_archived_lock(delete)
    assert back_to_draft.status_code == 409
    assert back_to_draft.json()["detail"] == INVALID_TRANSITION_MESSAGE
    assert _version_snapshot(db_session) == before


# --- Task 65: a new version is always a DRAFT ---


@pytest.mark.parametrize("status", ["PUBLISHED", "ARCHIVED"])
def test_create_version_with_non_draft_status_returns_422(
    client: TestClient, db_session: Session, status: str
) -> None:
    builder = Builder(db_session)
    before = _version_snapshot(db_session)

    response = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": builder.semester.id, "version_number": 1, "status": status},
    )

    assert response.status_code == 422
    assert _version_snapshot(db_session) == before


def test_create_version_defaults_to_draft(client: TestClient, db_session: Session) -> None:
    builder = Builder(db_session)

    response = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": builder.semester.id, "version_number": 1},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"


def test_failed_publish_rolls_back_the_archive(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The old version has already been archived (and flushed) when the
    # final step fails -- the rollback must restore it.
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    v2 = builder.version(number=2)
    v1_row = db_session.get(ScheduleVersion, v1.id)
    assert v1_row is not None
    v1_row.status = "PUBLISHED"
    db_session.commit()

    def fail(schedule_version: ScheduleVersion) -> None:
        raise RuntimeError("simulated failure while publishing")

    monkeypatch.setattr(schedule_version_service, "_mark_published", fail)

    with pytest.raises(RuntimeError):
        schedule_version_service.update_schedule_version(
            db_session, v2.id, ScheduleVersionUpdate(status="PUBLISHED")
        )

    assert _statuses(db_session, v1, v2) == ["PUBLISHED", "DRAFT"]


def test_database_allows_only_one_published_per_semester(db_session: Session) -> None:
    builder = Builder(db_session)
    db_session.add(
        ScheduleVersion(semester_id=builder.semester.id, version_number=1, status="PUBLISHED")
    )
    db_session.commit()
    db_session.add(
        ScheduleVersion(semester_id=builder.semester.id, version_number=2, status="PUBLISHED")
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- ARCHIVED is locked like PUBLISHED ---


def _assert_archived_lock(response: Any) -> None:
    assert response.status_code == 409
    assert response.json()["detail"] == ARCHIVED_LOCKED_MESSAGE


def test_archived_schedule_rows_are_locked(client: TestClient, db_session: Session) -> None:
    world, _ = _archived_world(client, db_session)
    row = _rows_of(db_session, world.version.id, world.english_requirement.id)[0]
    unscheduled_class = world.builder.class_("一年丙班")
    unscheduled = world.builder.course(
        world.version, unscheduled_class, world.english, None, [], unscheduled_periods=1
    )
    unscheduled_lesson = db_session.scalars(
        select(Lesson).where(Lesson.class_subject_requirement_id == unscheduled.id)
    ).one()
    before = _full_snapshot(db_session)

    create = client.post(
        "/api/v1/schedules/",
        json={
            "schedule_version_id": world.version.id,
            "lesson_id": unscheduled_lesson.id,
            "teacher_id": world.old_teacher.id,
            "time_slot_id": world.builder.slots[5].id,
        },
    )
    update = client.patch(
        f"/api/v1/schedules/{row.id}", json={"teacher_id": world.new_teacher.id}
    )
    delete = client.delete(f"/api/v1/schedules/{row.id}")

    for response in (create, update, delete):
        _assert_archived_lock(response)
    assert _full_snapshot(db_session) == before


def test_archived_version_cannot_be_deleted_or_edited(
    client: TestClient, db_session: Session
) -> None:
    world, _ = _archived_world(client, db_session)
    before = _full_snapshot(db_session)

    delete = client.delete(f"/api/v1/schedule-versions/{world.version.id}")
    edit = _patch(client, world.version.id, {"version_number": 9})
    edit_and_publish = _patch(
        client, world.version.id, {"version_number": 9, "status": "PUBLISHED"}
    )

    for response in (delete, edit, edit_and_publish):
        _assert_archived_lock(response)
    assert _full_snapshot(db_session) == before


def test_archived_version_blocks_reassign_run_scheduler_and_generate_lessons(
    client: TestClient, db_session: Session
) -> None:
    world, _ = _archived_world(client, db_session)
    before = _full_snapshot(db_session)

    reassign = client.post(
        f"/api/v1/schedule-versions/{world.version.id}/reassign-teacher",
        json={
            "class_subject_requirement_id": world.english_requirement.id,
            "new_teacher_id": world.new_teacher.id,
        },
    )
    run = client.post(f"/api/v1/schedule-versions/{world.version.id}/run-scheduler")
    generate = client.post(
        f"/api/v1/schedule-versions/{world.version.id}/generate-lessons"
    )

    for response in (reassign, run, generate):
        _assert_archived_lock(response)
    assert _full_snapshot(db_session) == before


def test_archived_version_can_be_copied_and_checked(
    client: TestClient, db_session: Session
) -> None:
    world, _ = _archived_world(client, db_session)

    check = client.get(f"/api/v1/schedule-versions/{world.version.id}/check")
    copy = client.post(f"/api/v1/schedule-versions/{world.version.id}/copy")

    assert check.status_code == 200
    assert check.json()["is_valid"] is True
    assert copy.status_code == 201
    assert copy.json()["status"] == "DRAFT"
    assert _statuses(db_session, world.version) == ["ARCHIVED"]


# --- Visibility ---


def test_teacher_cannot_see_archived_versions(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world, v2 = _archived_world(client, db_session)
    archived_id = world.version.id

    listed_ids = [v["id"] for v in teacher_client.get("/api/v1/schedule-versions/").json()]
    archived_one = teacher_client.get(f"/api/v1/schedule-versions/{archived_id}")
    published_one = teacher_client.get(f"/api/v1/schedule-versions/{v2.id}")
    archived_check = teacher_client.get(f"/api/v1/schedule-versions/{archived_id}/check")
    schedule_version_ids = {
        s["schedule_version_id"] for s in teacher_client.get("/api/v1/schedules/").json()
    }

    assert listed_ids == [v2.id]
    assert archived_one.status_code == 404
    assert published_one.status_code == 200
    # Task 72: the check is ADMIN-only now (403 for any version), not a
    # visibility-based 404.
    assert archived_check.status_code == 403
    assert archived_id not in schedule_version_ids
    # ADMIN still sees every version.
    admin_ids = {v["id"] for v in client.get("/api/v1/schedule-versions/").json()}
    assert {archived_id, v2.id} <= admin_ids


# --- Requirement delete rule (Task 56) ---


def test_requirement_used_by_archived_version_cannot_be_deleted(
    client: TestClient, db_session: Session
) -> None:
    world, _ = _archived_world(client, db_session)
    before = _full_snapshot(db_session)

    response = client.delete(
        f"/api/v1/class-subject-requirements/{world.english_requirement.id}"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "此排課需求已被已發布或已封存的課表使用，無法刪除"
    assert _full_snapshot(db_session) == before


def test_requirement_used_only_by_draft_is_deleted_with_its_rows(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    requirement_id = world.english_requirement.id

    response = client.delete(f"/api/v1/class-subject-requirements/{requirement_id}")

    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.get(ClassSubjectRequirement, requirement_id) is None
    assert _rows_of(db_session, world.version.id, requirement_id) == []


# --- Permissions ---


def test_teacher_cannot_change_status(
    teacher_client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)
    before = _version_snapshot(db_session)

    response = _patch(teacher_client, v1.id, {"status": "PUBLISHED"})

    assert response.status_code == 403
    assert _version_snapshot(db_session) == before


def test_unauthenticated_cannot_change_status(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session)
    v1 = builder.version(number=1)

    response = _patch(unauthenticated_client, v1.id, {"status": "PUBLISHED"})

    assert response.status_code == 401
    assert _statuses(db_session, v1) == ["DRAFT"]
