from collections import Counter
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.teacher import Teacher
from app.services import schedule_copy
from tests.test_schedule_check import (
    CheckSetup,
    _add_schedule,
    _build_setup,
    _place_both_lessons_in_same_slot,
)

# Task 62: POST /api/v1/schedule-versions/{id}/copy. The source timetable
# comes from test_schedule_check.py's _build_setup() (two classes, one
# 1-period requirement each, one qualified teacher, two time slots), written
# straight to the database through db_session.


@dataclass
class CopySetup:
    source: CheckSetup
    target_semester_id: int  # same academic year, no requirements yet
    room_id: int


def _build_copy_setup(db: Session) -> CopySetup:
    """Source semester (number 1) with a valid timetable: lesson 0 in slot 0
    with a room, lesson 1 in slot 1 (that lesson is also fixed to slot 1),
    plus an empty number-2 semester in the same academic year."""
    source = _build_setup(db)
    source_semester = db.get(Semester, source.semester_id)
    assert source_semester is not None
    target_semester = Semester(
        academic_year_id=source_semester.academic_year_id, number=2, is_active=True
    )
    room = Room(name="Room A", room_type="一般教室", is_active=True)
    db.add_all([target_semester, room])
    db.flush()

    fixed_lesson = db.get(Lesson, source.lesson_ids[1])
    assert fixed_lesson is not None
    fixed_lesson.fixed_time_slot_id = source.time_slot_ids[1]
    db.add_all(
        [
            Schedule(
                schedule_version_id=source.version_id,
                lesson_id=source.lesson_ids[0],
                teacher_id=source.teacher_id,
                time_slot_id=source.time_slot_ids[0],
                room_id=room.id,
            ),
            Schedule(
                schedule_version_id=source.version_id,
                lesson_id=source.lesson_ids[1],
                teacher_id=source.teacher_id,
                time_slot_id=source.time_slot_ids[1],
                room_id=None,
            ),
        ]
    )
    db.commit()
    return CopySetup(source=source, target_semester_id=target_semester.id, room_id=room.id)


def _build_copy_setup_without_schedules(db: Session) -> CopySetup:
    source = _build_setup(db)
    source_semester = db.get(Semester, source.semester_id)
    assert source_semester is not None
    target_semester = Semester(
        academic_year_id=source_semester.academic_year_id, number=2, is_active=True
    )
    room = Room(name="Room A", room_type="一般教室", is_active=True)
    db.add_all([target_semester, room])
    db.commit()
    return CopySetup(source=source, target_semester_id=target_semester.id, room_id=room.id)


def _copy(client: TestClient, version_id: int, body: dict | None = None) -> Any:
    url = f"/api/v1/schedule-versions/{version_id}/copy"
    return client.post(url) if body is None else client.post(url, json=body)


def _copy_cross(client: TestClient, setup: CopySetup) -> dict:
    response = _copy(
        client, setup.source.version_id, {"target_semester_id": setup.target_semester_id}
    )
    assert response.status_code == 201
    data: dict = response.json()
    return data


def _check(client: TestClient, version_id: int) -> dict:
    response = client.get(f"/api/v1/schedule-versions/{version_id}/check")
    assert response.status_code == 200
    data: dict = response.json()
    return data


def _requirements_of(db: Session, semester_id: int) -> list[ClassSubjectRequirement]:
    db.expire_all()
    return list(
        db.scalars(
            select(ClassSubjectRequirement)
            .where(ClassSubjectRequirement.semester_id == semester_id)
            .order_by(ClassSubjectRequirement.id)
        ).all()
    )


def _lessons_of(db: Session, semester_id: int) -> list[Lesson]:
    requirement_ids = [r.id for r in _requirements_of(db, semester_id)]
    return list(
        db.scalars(
            select(Lesson)
            .where(Lesson.class_subject_requirement_id.in_(requirement_ids))
            .order_by(Lesson.id)
        ).all()
    )


def _schedules_of(db: Session, version_id: int) -> list[Schedule]:
    db.expire_all()
    return list(
        db.scalars(
            select(Schedule)
            .where(Schedule.schedule_version_id == version_id)
            .order_by(Schedule.id)
        ).all()
    )


def _row_counts(db: Session) -> dict[str, int]:
    db.expire_all()
    return {
        model.__name__: db.scalar(select(func.count()).select_from(model)) or 0
        for model in (ScheduleVersion, ClassSubjectRequirement, Lesson, Schedule)
    }


def _full_snapshot(db: Session) -> list[tuple[object, ...]]:
    """Every column of every requirement/Lesson/Schedule/version row --
    used to prove the source is byte-for-byte untouched."""
    db.expire_all()
    snapshot: list[tuple[object, ...]] = []
    for model in (ScheduleVersion, ClassSubjectRequirement, Lesson, Schedule):
        columns = list(model.__table__.columns.keys())
        for row in db.scalars(select(model).order_by(model.id)).all():
            snapshot.append(
                (model.__name__, *(getattr(row, column) for column in columns))
            )
    return snapshot


# --- Cross-semester copy ---


def test_copy_cross_semester_creates_draft_version_1(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    data = _copy_cross(client, setup)

    assert data["status"] == "DRAFT"
    assert data["semester_id"] == setup.target_semester_id
    assert data["version_number"] == 1
    assert data["id"] != setup.source.version_id


def test_copy_cross_semester_copies_requirements(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    source_requirement = db_session.get(
        ClassSubjectRequirement, setup.source.requirement_ids[0]
    )
    assert source_requirement is not None
    source_requirement.required_teacher_id = setup.source.teacher_id
    source_requirement.required_room_type = "一般教室"
    source_requirement.consecutive_limit = 2
    db_session.commit()

    _copy_cross(client, setup)

    source_rows = _requirements_of(db_session, setup.source.semester_id)
    copied_rows = _requirements_of(db_session, setup.target_semester_id)
    assert len(copied_rows) == len(source_rows) == 2
    for source_row, copied_row in zip(source_rows, copied_rows):
        assert copied_row.semester_id == setup.target_semester_id
        assert copied_row.id != source_row.id
        for field in schedule_copy.COPIED_REQUIREMENT_FIELDS:
            assert getattr(copied_row, field) == getattr(source_row, field), field


def test_copy_requirement_field_lists_cover_every_column() -> None:
    # Guards COPIED_REQUIREMENT_FIELDS: a column added to the model later
    # must be consciously put in one list or the other, never silently
    # left out of the copy.
    copied = set(schedule_copy.COPIED_REQUIREMENT_FIELDS)
    not_copied = set(schedule_copy.NOT_COPIED_REQUIREMENT_FIELDS)
    assert copied.isdisjoint(not_copied)
    assert copied | not_copied == set(ClassSubjectRequirement.__table__.columns.keys())


def test_copy_cross_semester_copies_lessons(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    _copy_cross(client, setup)

    source_lessons = _lessons_of(db_session, setup.source.semester_id)
    copied_lessons = _lessons_of(db_session, setup.target_semester_id)
    new_requirement_ids = {r.id for r in _requirements_of(db_session, setup.target_semester_id)}
    assert len(copied_lessons) == len(source_lessons) == 2
    for source_lesson, copied_lesson in zip(source_lessons, copied_lessons):
        assert copied_lesson.class_subject_requirement_id in new_requirement_ids
        assert copied_lesson.sequence_number == source_lesson.sequence_number
        assert copied_lesson.fixed_time_slot_id == source_lesson.fixed_time_slot_id
    assert copied_lessons[1].fixed_time_slot_id == setup.source.time_slot_ids[1]


def test_copy_cross_semester_copies_schedule_rows(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    data = _copy_cross(client, setup)

    source_rows = _schedules_of(db_session, setup.source.version_id)
    copied_rows = _schedules_of(db_session, data["id"])
    new_lesson_ids = {lesson.id for lesson in _lessons_of(db_session, setup.target_semester_id)}
    assert len(copied_rows) == len(source_rows) == 2
    for source_row, copied_row in zip(source_rows, copied_rows):
        assert copied_row.teacher_id == source_row.teacher_id
        assert copied_row.time_slot_id == source_row.time_slot_id
        assert copied_row.room_id == source_row.room_id
        assert copied_row.lesson_id in new_lesson_ids
        assert copied_row.lesson_id not in setup.source.lesson_ids
    assert copied_rows[0].room_id == setup.room_id


def test_copy_of_valid_timetable_is_valid(client: TestClient, db_session: Session) -> None:
    setup = _build_copy_setup(db_session)
    assert _check(client, setup.source.version_id)["is_valid"] is True

    data = _copy_cross(client, setup)

    assert _check(client, data["id"])["is_valid"] is True


def test_copy_of_conflicting_timetable_has_same_violations(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup_without_schedules(db_session)
    _place_both_lessons_in_same_slot(db_session, setup.source)
    source_check = _check(client, setup.source.version_id)
    assert source_check["is_valid"] is False

    data = _copy_cross(client, setup)

    copy_check = _check(client, data["id"])
    assert Counter(v["type"] for v in copy_check["violations"]) == Counter(
        v["type"] for v in source_check["violations"]
    )


def test_copy_does_not_modify_source(client: TestClient, db_session: Session) -> None:
    setup = _build_copy_setup(db_session)
    before = _full_snapshot(db_session)

    data = _copy_cross(client, setup)

    after = [row for row in _full_snapshot(db_session) if not _is_new_row(row, data, setup)]
    assert after == before


def _is_new_row(row: tuple[object, ...], data: dict, setup: CopySetup) -> bool:
    """True for a row the copy created (so the remaining rows can be
    compared against the pre-copy snapshot)."""
    model_name, row_id = row[0], row[1]
    if model_name == "ScheduleVersion":
        return row_id == data["id"]
    if model_name == "ClassSubjectRequirement":
        return row_id not in setup.source.requirement_ids
    if model_name == "Lesson":
        return row_id not in setup.source.lesson_ids
    # Schedule: (name, id, schedule_version_id, ...) in column order.
    columns = list(Schedule.__table__.columns.keys())
    return row[1 + columns.index("schedule_version_id")] == data["id"]


def test_copy_published_source_creates_draft(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    source_version = db_session.get(ScheduleVersion, setup.source.version_id)
    assert source_version is not None
    source_version.status = "PUBLISHED"
    db_session.commit()

    data = _copy_cross(client, setup)

    assert data["status"] == "DRAFT"
    db_session.expire_all()
    assert db_session.get(ScheduleVersion, setup.source.version_id).status == "PUBLISHED"


def test_copy_source_without_schedule_rows(client: TestClient, db_session: Session) -> None:
    setup = _build_copy_setup_without_schedules(db_session)

    data = _copy_cross(client, setup)

    assert len(_requirements_of(db_session, setup.target_semester_id)) == 2
    assert len(_lessons_of(db_session, setup.target_semester_id)) == 2
    assert _schedules_of(db_session, data["id"]) == []


def test_copy_keeps_inactive_required_teacher(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    source_requirement = db_session.get(
        ClassSubjectRequirement, setup.source.requirement_ids[0]
    )
    teacher = db_session.get(Teacher, setup.source.teacher_id)
    assert source_requirement is not None and teacher is not None
    source_requirement.required_teacher_id = teacher.id
    teacher.is_active = False
    db_session.commit()

    data = _copy_cross(client, setup)

    copied_requirements = _requirements_of(db_session, setup.target_semester_id)
    assert copied_requirements[0].required_teacher_id == setup.source.teacher_id
    violation_types = {v["type"] for v in _check(client, data["id"])["violations"]}
    assert "H12_ACTIVE_STATUS" in violation_types


def test_copy_keeps_null_time_slot(client: TestClient, db_session: Session) -> None:
    setup = _build_copy_setup_without_schedules(db_session)
    _add_schedule(db_session, setup.source, setup.source.lesson_ids[0], setup.source.time_slot_ids[0])
    db_session.add(
        Schedule(
            schedule_version_id=setup.source.version_id,
            lesson_id=setup.source.lesson_ids[1],
            teacher_id=setup.source.teacher_id,
            time_slot_id=None,
            room_id=None,
        )
    )
    db_session.commit()

    data = _copy_cross(client, setup)

    copied_rows = _schedules_of(db_session, data["id"])
    assert [row.time_slot_id for row in copied_rows] == [setup.source.time_slot_ids[0], None]
    violation_types = {v["type"] for v in _check(client, data["id"])["violations"]}
    assert "INCOMPLETE_SCHEDULE_ROW" in violation_types


# --- Cross-semester refusals: nothing may be created ---


def test_copy_to_other_academic_year_returns_409(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    other_year = AcademicYear(year=9001, is_active=True)
    db_session.add(other_year)
    db_session.flush()
    other_semester = Semester(academic_year_id=other_year.id, number=1, is_active=True)
    db_session.add(other_semester)
    db_session.commit()
    before = _row_counts(db_session)

    response = _copy(
        client, setup.source.version_id, {"target_semester_id": other_semester.id}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "目標學期與來源課表不在同一學年，無法複製"
    assert _row_counts(db_session) == before


def test_copy_to_semester_with_requirements_returns_409(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    existing = _requirements_of(db_session, setup.source.semester_id)[0]
    db_session.add(
        ClassSubjectRequirement(
            semester_id=setup.target_semester_id,
            class_id=existing.class_id,
            subject_id=existing.subject_id,
            weekly_periods=1,
        )
    )
    db_session.commit()
    before = _row_counts(db_session)

    response = _copy(
        client, setup.source.version_id, {"target_semester_id": setup.target_semester_id}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "目標學期已有排課需求，無法複製"
    assert _row_counts(db_session) == before


def test_copy_to_missing_semester_returns_404(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    before = _row_counts(db_session)

    response = _copy(client, setup.source.version_id, {"target_semester_id": 999999})

    assert response.status_code == 404
    assert response.json()["detail"] == "目標學期不存在"
    assert _row_counts(db_session) == before


def test_copy_missing_source_returns_404(client: TestClient) -> None:
    response = _copy(client, 999999)

    assert response.status_code == 404
    assert response.json()["detail"] == "ScheduleVersion not found"


def test_copy_failure_part_way_leaves_nothing_behind(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fails AFTER the new version, requirements and Lessons are already
    # staged (and flushed) -- the rollback must undo all of them.
    setup = _build_copy_setup(db_session)
    before = _row_counts(db_session)

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated failure while copying Schedule rows")

    monkeypatch.setattr(schedule_copy, "_stage_schedule_copies", fail)

    with pytest.raises(RuntimeError):
        schedule_copy.copy_schedule_version(
            db_session, setup.source.version_id, setup.target_semester_id
        )

    assert _row_counts(db_session) == before
    assert _requirements_of(db_session, setup.target_semester_id) == []


# --- Same-semester copy ---


def test_copy_same_semester_with_omitted_or_explicit_target(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    omitted = _copy(client, setup.source.version_id)
    no_target = _copy(client, setup.source.version_id, {})
    explicit = _copy(
        client, setup.source.version_id, {"target_semester_id": setup.source.semester_id}
    )

    for response in (omitted, no_target, explicit):
        assert response.status_code == 201
        assert response.json()["semester_id"] == setup.source.semester_id
        assert response.json()["status"] == "DRAFT"
    assert [r.json()["version_number"] for r in (omitted, no_target, explicit)] == [2, 3, 4]


def test_copy_same_semester_uses_max_version_number_and_shares_lessons(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    db_session.add(
        ScheduleVersion(semester_id=setup.source.semester_id, version_number=5, status="DRAFT")
    )
    db_session.commit()
    requirement_count = len(_requirements_of(db_session, setup.source.semester_id))
    lesson_count = db_session.scalar(select(func.count()).select_from(Lesson))

    response = _copy(client, setup.source.version_id)

    assert response.status_code == 201
    assert response.json()["version_number"] == 6
    assert len(_requirements_of(db_session, setup.source.semester_id)) == requirement_count
    assert db_session.scalar(select(func.count()).select_from(Lesson)) == lesson_count


def test_copy_same_semester_points_at_same_lessons(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    response = _copy(client, setup.source.version_id)

    source_rows = _schedules_of(db_session, setup.source.version_id)
    copied_rows = _schedules_of(db_session, response.json()["id"])
    assert [
        (r.lesson_id, r.teacher_id, r.time_slot_id, r.room_id) for r in copied_rows
    ] == [(r.lesson_id, r.teacher_id, r.time_slot_id, r.room_id) for r in source_rows]


def test_editing_copy_does_not_affect_source(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    other_teacher = Teacher(
        name="Other teacher", is_active=True, min_weekly_periods=0, max_weekly_periods=20
    )
    db_session.add(other_teacher)
    db_session.commit()
    source_before = [
        (r.id, r.teacher_id) for r in _schedules_of(db_session, setup.source.version_id)
    ]

    copy_id = _copy(client, setup.source.version_id).json()["id"]
    copied_row = _schedules_of(db_session, copy_id)[0]
    patch_response = client.patch(
        f"/api/v1/schedules/{copied_row.id}", json={"teacher_id": other_teacher.id}
    )

    assert patch_response.status_code == 200
    assert _schedules_of(db_session, copy_id)[0].teacher_id == other_teacher.id
    assert [
        (r.id, r.teacher_id) for r in _schedules_of(db_session, setup.source.version_id)
    ] == source_before


# --- Permissions ---


def test_copy_unauthenticated_returns_401(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    response = _copy(unauthenticated_client, setup.source.version_id)

    assert response.status_code == 401


def test_copy_as_teacher_returns_403(teacher_client: TestClient, db_session: Session) -> None:
    setup = _build_copy_setup(db_session)
    before = _row_counts(db_session)

    response = _copy(teacher_client, setup.source.version_id)

    assert response.status_code == 403
    assert _row_counts(db_session) == before
