from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_year import Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.subject import Subject
from app.models.teacher import Teacher
from tests.test_reassign_teacher import Builder

# Task 72: PATCH /class-subject-requirements/{id} refuses to change any
# field of a requirement whose lessons are placed in a PUBLISHED or ARCHIVED
# version (409, the same condition as the delete guard). Only-DRAFT and
# unused requirements are unaffected; reassign-teacher on a DRAFT still
# works. Test data is written straight to the database.

LOCKED_MESSAGE = "此排課需求已被已發布或已封存的課表使用，無法修改"


@dataclass
class EditWorld:
    builder: Builder
    requirement: ClassSubjectRequirement  # placed in `version`
    version: ScheduleVersion
    other_class: Class
    other_subject: Subject
    other_teacher: Teacher
    other_semester_id: int


def _build_world(db: Session, *, placed: bool = True) -> EditWorld:
    builder = Builder(db)
    other_semester = builder.semester_in_year(number=2)
    english = builder.subject("英文")
    science = builder.subject("自然")
    teacher = builder.teacher("一號老師", [english, science])
    other_teacher = builder.teacher("二號老師", [english, science])
    class_ = builder.class_("一班")
    other_class = builder.class_("二班")
    version = builder.version()
    requirement = builder.course(
        version,
        class_,
        english,
        teacher,
        [0, 1] if placed else [],
        required_teacher=teacher,
        unscheduled_periods=0 if placed else 2,
    )
    return EditWorld(
        builder=builder,
        requirement=requirement,
        version=version,
        other_class=other_class,
        other_subject=science,
        other_teacher=other_teacher,
        other_semester_id=other_semester.id,
    )


def _set_status(db: Session, version: ScheduleVersion, status: str) -> None:
    version.status = status
    db.commit()


# One changed value per editable field.
def _changes(world: EditWorld) -> dict[str, Any]:
    return {
        "class_id": world.other_class.id,
        "subject_id": world.other_subject.id,
        "semester_id": world.other_semester_id,
        "weekly_periods": world.requirement.weekly_periods + 1,
        "required_teacher_id": world.other_teacher.id,
        "required_room_type": "專科教室",
        "consecutive_limit": 2,
    }


FIELDS = [
    "class_id",
    "subject_id",
    "semester_id",
    "weekly_periods",
    "required_teacher_id",
    "required_room_type",
    "consecutive_limit",
]


def _patch(client: TestClient, requirement_id: int, body: dict[str, Any]) -> Any:
    return client.patch(f"/api/v1/class-subject-requirements/{requirement_id}", json=body)


def _snapshot(db: Session, requirement_id: int) -> tuple[object, ...]:
    db.expire_all()
    requirement = db.get(ClassSubjectRequirement, requirement_id)
    assert requirement is not None
    return tuple(getattr(requirement, field) for field in FIELDS)


@pytest.mark.parametrize("status", ["PUBLISHED", "ARCHIVED"])
@pytest.mark.parametrize("field", FIELDS)
def test_locked_requirement_field_change_is_refused(
    client: TestClient, db_session: Session, status: str, field: str
) -> None:
    world = _build_world(db_session)
    _set_status(db_session, world.version, status)
    before = _snapshot(db_session, world.requirement.id)

    response = _patch(client, world.requirement.id, {field: _changes(world)[field]})

    assert response.status_code == 409
    assert response.json()["detail"] == LOCKED_MESSAGE
    assert _snapshot(db_session, world.requirement.id) == before


@pytest.mark.parametrize("status", ["PUBLISHED", "ARCHIVED"])
def test_locked_requirement_same_values_are_not_an_edit(
    client: TestClient, db_session: Session, status: str
) -> None:
    # Sending the current values changes nothing, so nothing is refused.
    world = _build_world(db_session)
    _set_status(db_session, world.version, status)
    current = dict(zip(FIELDS, _snapshot(db_session, world.requirement.id)))

    response = _patch(client, world.requirement.id, current)

    assert response.status_code == 200


def test_requirement_used_only_by_draft_can_change_every_field(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    changes = _changes(world)

    response = _patch(client, world.requirement.id, changes)

    assert response.status_code == 200
    assert {field: response.json()[field] for field in FIELDS} == changes


def test_unused_requirement_can_change_every_field(
    client: TestClient, db_session: Session
) -> None:
    # Lessons exist but no version places them.
    world = _build_world(db_session, placed=False)
    assert db_session.scalars(select(Schedule)).first() is None

    response = _patch(client, world.requirement.id, _changes(world))

    assert response.status_code == 200


def test_requirement_lock_does_not_depend_on_other_semesters_versions(
    client: TestClient, db_session: Session
) -> None:
    # A PUBLISHED version elsewhere doesn't lock a requirement only a
    # DRAFT uses.
    world = _build_world(db_session)
    other_semester = db_session.get(Semester, world.other_semester_id)
    assert other_semester is not None
    other_version = world.builder.version(semester=other_semester)
    _set_status(db_session, other_version, "PUBLISHED")

    response = _patch(client, world.requirement.id, {"weekly_periods": 3})

    assert response.status_code == 200


def test_delete_guard_still_refuses_locked_requirement(
    client: TestClient, db_session: Session
) -> None:
    # The delete guard now shares is_used_by_locked_schedule() with PATCH.
    world = _build_world(db_session)
    _set_status(db_session, world.version, "PUBLISHED")

    response = client.delete(f"/api/v1/class-subject-requirements/{world.requirement.id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "此排課需求已被已發布或已封存的課表使用，無法刪除"


def test_reassign_on_draft_still_works_when_semester_has_published_version(
    client: TestClient, db_session: Session
) -> None:
    # Decision 17: reassign-teacher updates the shared requirement directly
    # in its service -- not through PATCH -- and only on a DRAFT. The edit
    # guard must not get in its way even though the requirement is now
    # used by a PUBLISHED version.
    world = _build_world(db_session)
    _set_status(db_session, world.version, "PUBLISHED")
    copy_response = client.post(f"/api/v1/schedule-versions/{world.version.id}/copy")
    assert copy_response.status_code == 201
    draft_id = copy_response.json()["id"]
    published_rows_before = [
        (row.id, row.teacher_id)
        for row in db_session.scalars(
            select(Schedule).where(Schedule.schedule_version_id == world.version.id)
        ).all()
    ]
    # PATCH on the same requirement is refused...
    assert (
        _patch(client, world.requirement.id, {"required_teacher_id": world.other_teacher.id})
        .status_code
        == 409
    )

    # ...but reassigning in the DRAFT succeeds.
    response = client.post(
        f"/api/v1/schedule-versions/{draft_id}/reassign-teacher",
        json={
            "class_subject_requirement_id": world.requirement.id,
            "new_teacher_id": world.other_teacher.id,
        },
    )

    assert response.status_code == 200
    assert response.json()["updated_schedule_row_count"] == 2
    db_session.expire_all()
    assert (
        db_session.get(ClassSubjectRequirement, world.requirement.id).required_teacher_id
        == world.other_teacher.id
    )
    # The PUBLISHED version's rows are untouched.
    assert [
        (row.id, row.teacher_id)
        for row in db_session.scalars(
            select(Schedule).where(Schedule.schedule_version_id == world.version.id)
        ).all()
    ] == published_rows_before
