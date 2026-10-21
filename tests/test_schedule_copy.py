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
from app.models.semester_grade_time_slot import SemesterGradeTimeSlot
from app.models.teacher import Teacher
from app.services import schedule_copy, version_contents
from tests.test_schedule_check import (
    CheckSetup,
    _add_schedule,
    _build_setup,
    _place_both_lessons_in_same_slot,
)
from tests.conftest import get_test_school_id, mark_status_in_db

# Task 62 / v3: the two copies of a 排課紀錄.
# - POST /schedule-versions/{id}/copy (複製此課表): settings and timetable
#   into a new 複製自編號 x record, of any semester of the same academic year.
# - POST /schedule-versions/{id}/copy-settings (複製此次排課設定): settings
#   only, into a new 尚未排課 record of the same semester.
# The source comes from test_schedule_check.py's _build_setup() (two
# classes, one 1-period requirement each, one teacher taking part, two time
# slots), written straight to the database through db_session.


@dataclass
class CopySetup:
    source: CheckSetup
    target_semester_id: int  # same academic year
    room_id: int


def _add_semester_and_room(db: Session, source: CheckSetup) -> tuple[Semester, Room]:
    source_semester = db.get(Semester, source.semester_id)
    assert source_semester is not None
    target_semester = Semester(
        academic_year_id=source_semester.academic_year_id, number=2, is_active=True
    )
    room = Room(school_id=get_test_school_id(db), name="Room A", is_active=True)
    db.add_all([target_semester, room])
    db.flush()
    return target_semester, room


def _build_copy_setup(db: Session) -> CopySetup:
    """Source record (自動排課, semester number 1) with a valid timetable:
    lesson 0 in slot 0 with a room, lesson 1 in slot 1 (that lesson is also
    fixed to slot 1), plus a number-2 semester in the same academic year."""
    source = _build_setup(db)
    target_semester, room = _add_semester_and_room(db, source)

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
    db.add_all(
        SemesterGradeTimeSlot(
            schedule_version_id=source.version_id,
            grade_id=_grade_id(db, source),
            time_slot_id=time_slot_id,
        )
        for time_slot_id in source.time_slot_ids
    )
    db.commit()
    mark_status_in_db(db, source.version_id, "AUTO")
    return CopySetup(source=source, target_semester_id=target_semester.id, room_id=room.id)


def _build_copy_setup_without_schedules(db: Session) -> CopySetup:
    """The same source record with no Schedule rows yet -- 自動排課 all the
    same, so tests can place its rows themselves."""
    source = _build_setup(db)
    target_semester, room = _add_semester_and_room(db, source)
    db.commit()
    mark_status_in_db(db, source.version_id, "AUTO")
    return CopySetup(source=source, target_semester_id=target_semester.id, room_id=room.id)


def _grade_id(db: Session, source: CheckSetup) -> int:
    requirement = db.get(ClassSubjectRequirement, source.requirement_ids[0])
    assert requirement is not None
    return requirement.class_.grade_id


def _copy(client: TestClient, version_id: int, body: dict | None = None) -> Any:
    url = f"/api/v1/schedule-versions/{version_id}/copy"
    return client.post(url) if body is None else client.post(url, json=body)


def _copy_cross(client: TestClient, setup: CopySetup) -> dict:
    response = _copy(
        client, setup.source.version_id, {"target_semester_id": setup.target_semester_id}
    )
    assert response.status_code == 201, response.json()
    data: dict = response.json()
    return data


def _copy_settings(client: TestClient, version_id: int) -> Any:
    return client.post(f"/api/v1/schedule-versions/{version_id}/copy-settings")


def _check(client: TestClient, version_id: int) -> dict:
    response = client.get(f"/api/v1/schedule-versions/{version_id}/check")
    assert response.status_code == 200
    data: dict = response.json()
    return data


def _requirements_of(db: Session, version_id: int) -> list[ClassSubjectRequirement]:
    db.expire_all()
    return list(
        db.scalars(
            select(ClassSubjectRequirement)
            .where(ClassSubjectRequirement.schedule_version_id == version_id)
            .order_by(ClassSubjectRequirement.id)
        ).all()
    )


def _lessons_of(db: Session, version_id: int) -> list[Lesson]:
    requirement_ids = [r.id for r in _requirements_of(db, version_id)]
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


def _grade_slots_of(db: Session, version_id: int) -> list[tuple[int, int]]:
    db.expire_all()
    return sorted(
        (row.grade_id, row.time_slot_id)
        for row in db.scalars(
            select(SemesterGradeTimeSlot).where(
                SemesterGradeTimeSlot.schedule_version_id == version_id
            )
        ).all()
    )


def _teachers_of(client: TestClient, version_id: int) -> list[dict]:
    response = client.get(f"/api/v1/schedule-versions/{version_id}/teachers")
    assert response.status_code == 200
    data: list[dict] = response.json()
    return data


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


def _source_number(db: Session, setup: CopySetup) -> int:
    db.expire_all()
    source = db.get(ScheduleVersion, setup.source.version_id)
    assert source is not None and source.version_number is not None
    return source.version_number


# --- 複製此課表: the new record ---


def test_copy_creates_a_copied_record_with_the_next_number(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    data = _copy_cross(client, setup)

    assert data["status"] == "COPIED"
    assert data["copied_from_number"] == _source_number(db_session, setup)
    assert data["semester_id"] == setup.target_semester_id
    assert data["version_number"] == _source_number(db_session, setup) + 1
    assert data["is_published"] is False
    assert data["id"] != setup.source.version_id


def _read(client: TestClient, version_id: int) -> dict:
    response = client.get(f"/api/v1/schedule-versions/{version_id}")
    assert response.status_code == 200, response.json()
    data: dict = response.json()
    return data


def test_display_numbers_count_from_the_newest_record(
    client: TestClient, db_session: Session
) -> None:
    """編號 as shown: the newest record is 1. A copy names its source by
    the source's 編號 now, which shifts as records are made and deleted;
    the stored serials never change."""
    setup = _build_copy_setup(db_session)
    copy = _copy_cross(client, setup)

    assert copy["display_number"] == 1
    assert copy["copied_from_display_number"] == 2
    assert _read(client, setup.source.version_id)["display_number"] == 2

    newer = client.post(
        "/api/v1/schedule-versions/", json={"semester_id": setup.target_semester_id}
    )
    assert newer.status_code == 201, newer.json()
    assert newer.json()["display_number"] == 1
    copy_now = _read(client, copy["id"])
    assert copy_now["display_number"] == 2
    assert copy_now["copied_from_display_number"] == 3
    assert copy_now["version_number"] == copy["version_number"]
    assert copy_now["copied_from_number"] == copy["copied_from_number"]

    listed = client.get("/api/v1/schedule-versions/").json()
    assert [item["display_number"] for item in listed] == list(range(1, len(listed) + 1))

    assert client.delete(f"/api/v1/schedule-versions/{setup.source.version_id}").status_code == 204
    copy_after = _read(client, copy["id"])
    assert copy_after["copied_from_display_number"] is None
    assert copy_after["copied_from_number"] == copy["copied_from_number"]


def test_copy_copies_requirements(client: TestClient, db_session: Session) -> None:
    setup = _build_copy_setup(db_session)
    source_requirement = db_session.get(
        ClassSubjectRequirement, setup.source.requirement_ids[0]
    )
    assert source_requirement is not None
    source_requirement.required_teacher_id = setup.source.teacher_id
    source_requirement.required_room_type = "一般教室"
    source_requirement.consecutive_limit = 2
    db_session.commit()

    data = _copy_cross(client, setup)

    source_rows = _requirements_of(db_session, setup.source.version_id)
    copied_rows = _requirements_of(db_session, data["id"])
    assert len(copied_rows) == len(source_rows) == 2
    for source_row, copied_row in zip(source_rows, copied_rows):
        assert copied_row.schedule_version_id == data["id"]
        assert copied_row.id != source_row.id
        for field in version_contents.COPIED_REQUIREMENT_FIELDS:
            assert getattr(copied_row, field) == getattr(source_row, field), field


def test_copy_requirement_field_lists_cover_every_column() -> None:
    # Guards COPIED_REQUIREMENT_FIELDS: a column added to the model later
    # must be consciously put in one list or the other, never silently
    # left out of the copy.
    copied = set(version_contents.COPIED_REQUIREMENT_FIELDS)
    not_copied = set(version_contents.NOT_COPIED_REQUIREMENT_FIELDS)
    assert copied.isdisjoint(not_copied)
    assert copied | not_copied == set(ClassSubjectRequirement.__table__.columns.keys())


def test_copy_copies_lessons(client: TestClient, db_session: Session) -> None:
    setup = _build_copy_setup(db_session)

    data = _copy_cross(client, setup)

    source_lessons = _lessons_of(db_session, setup.source.version_id)
    copied_lessons = _lessons_of(db_session, data["id"])
    new_requirement_ids = {r.id for r in _requirements_of(db_session, data["id"])}
    assert len(copied_lessons) == len(source_lessons) == 2
    for source_lesson, copied_lesson in zip(source_lessons, copied_lessons):
        assert copied_lesson.class_subject_requirement_id in new_requirement_ids
        assert copied_lesson.sequence_number == source_lesson.sequence_number
        assert copied_lesson.fixed_time_slot_id == source_lesson.fixed_time_slot_id
    assert copied_lessons[1].fixed_time_slot_id == setup.source.time_slot_ids[1]


def test_copy_copies_schedule_rows_onto_the_copied_lessons(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    data = _copy_cross(client, setup)

    source_rows = _schedules_of(db_session, setup.source.version_id)
    copied_rows = _schedules_of(db_session, data["id"])
    new_lesson_ids = {lesson.id for lesson in _lessons_of(db_session, data["id"])}
    assert len(copied_rows) == len(source_rows) == 2
    for source_row, copied_row in zip(source_rows, copied_rows):
        assert copied_row.teacher_id == source_row.teacher_id
        assert copied_row.time_slot_id == source_row.time_slot_id
        assert copied_row.room_id == source_row.room_id
        assert copied_row.lesson_id in new_lesson_ids
        assert copied_row.lesson_id not in setup.source.lesson_ids
    assert copied_rows[0].room_id == setup.room_id


def test_copy_copies_teachers_and_grade_slots(client: TestClient, db_session: Session) -> None:
    setup = _build_copy_setup(db_session)
    source_teachers = _teachers_of(client, setup.source.version_id)
    assert source_teachers != []

    data = _copy_cross(client, setup)

    assert _teachers_of(client, data["id"]) == source_teachers
    assert _grade_slots_of(db_session, data["id"]) == _grade_slots_of(
        db_session, setup.source.version_id
    )


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


@pytest.mark.parametrize("status", ["AUTO", "MANUAL", "COPIED"])
def test_copy_works_from_every_record_with_a_timetable(
    client: TestClient, db_session: Session, status: str
) -> None:
    setup = _build_copy_setup(db_session)
    mark_status_in_db(db_session, setup.source.version_id, status, is_published=True)

    data = _copy_cross(client, setup)

    assert data["status"] == "COPIED"
    assert data["is_published"] is False
    db_session.expire_all()
    source = db_session.get(ScheduleVersion, setup.source.version_id)
    assert source is not None and source.is_published is True


@pytest.mark.parametrize("status", ["NOT_SCHEDULED", "EDITING"])
def test_copy_of_a_record_without_a_timetable_returns_409(
    client: TestClient, db_session: Session, status: str
) -> None:
    setup = _build_copy_setup(db_session)
    mark_status_in_db(db_session, setup.source.version_id, status)
    before = _row_counts(db_session)

    response = _copy(client, setup.source.version_id)

    assert response.status_code == 409
    assert response.json()["detail"] == "這筆排課紀錄還沒有課表，無法複製課表"
    assert _row_counts(db_session) == before


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

    copied_requirements = _requirements_of(db_session, data["id"])
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


# --- 複製此課表: the target semester ---


def test_copy_same_semester_with_omitted_or_explicit_target(
    client: TestClient, db_session: Session
) -> None:
    """v3: any semester of the academic year, the source's own included."""
    setup = _build_copy_setup(db_session)
    first_number = _source_number(db_session, setup) + 1

    omitted = _copy(client, setup.source.version_id)
    no_target = _copy(client, setup.source.version_id, {})
    explicit = _copy(
        client, setup.source.version_id, {"target_semester_id": setup.source.semester_id}
    )

    for response in (omitted, no_target, explicit):
        assert response.status_code == 201
        assert response.json()["semester_id"] == setup.source.semester_id
        assert response.json()["status"] == "COPIED"
    assert [r.json()["version_number"] for r in (omitted, no_target, explicit)] == [
        first_number,
        first_number + 1,
        first_number + 2,
    ]


def test_a_same_semester_copy_has_its_own_settings(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    data = _copy(client, setup.source.version_id).json()

    copied_ids = {r.id for r in _requirements_of(db_session, data["id"])}
    assert len(copied_ids) == 2
    assert copied_ids.isdisjoint(setup.source.requirement_ids)


def test_copy_to_other_academic_year_returns_409(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    other_year = AcademicYear(school_id=get_test_school_id(db_session), year=9001, is_active=True)
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


def test_copy_to_a_semester_with_records_is_fine(
    client: TestClient, db_session: Session
) -> None:
    """v3: records never share settings, so a target semester that already
    has records (and their requirements) takes the copy as one more."""
    setup = _build_copy_setup(db_session)
    first = _copy_cross(client, setup)

    second = _copy_cross(client, setup)

    assert second["semester_id"] == first["semester_id"] == setup.target_semester_id
    assert len(_requirements_of(db_session, second["id"])) == 2


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
    # Fails AFTER the new record, requirements and Lessons are already
    # staged (and flushed) -- the rollback must undo all of them.
    setup = _build_copy_setup(db_session)
    before = _row_counts(db_session)

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated failure while copying Schedule rows")

    monkeypatch.setattr(schedule_copy, "stage_copy_timetable", fail)

    with pytest.raises(RuntimeError):
        schedule_copy.copy_timetable(
            db_session, setup.source.version_id, setup.target_semester_id
        )

    assert _row_counts(db_session) == before


# --- 複製此次排課設定 ---


def test_copy_settings_creates_a_not_scheduled_record_of_the_same_semester(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    response = _copy_settings(client, setup.source.version_id)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "NOT_SCHEDULED"
    assert data["semester_id"] == setup.source.semester_id
    assert data["copied_from_number"] is None
    assert data["version_number"] == _source_number(db_session, setup) + 1


def test_copy_settings_copies_every_setting_but_no_timetable(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    data = _copy_settings(client, setup.source.version_id).json()

    assert _teachers_of(client, data["id"]) == _teachers_of(client, setup.source.version_id)
    assert _grade_slots_of(db_session, data["id"]) == _grade_slots_of(
        db_session, setup.source.version_id
    )
    copied = _requirements_of(db_session, data["id"])
    assert [(r.class_id, r.subject_id, r.weekly_periods) for r in copied] == [
        (r.class_id, r.subject_id, r.weekly_periods)
        for r in _requirements_of(db_session, setup.source.version_id)
    ]
    # The lessons come along (a fixed slot is a setting too) ...
    assert [lesson.fixed_time_slot_id for lesson in _lessons_of(db_session, data["id"])] == [
        None,
        setup.source.time_slot_ids[1],
    ]
    # ... but not the timetable.
    assert _schedules_of(db_session, data["id"]) == []


def test_copied_settings_can_be_changed_and_scheduled(
    client: TestClient, db_session: Session
) -> None:
    """Item 12: the copy is 尚未排課 -- its settings change (the source's
    don't), and 自動排課 runs on it."""
    setup = _build_copy_setup(db_session)
    data = _copy_settings(client, setup.source.version_id).json()
    copied_requirement = _requirements_of(db_session, data["id"])[0]

    patched = client.patch(
        f"/api/v1/class-subject-requirements/{copied_requirement.id}",
        json={"lesson_pattern": None},
    )
    source_patch = client.patch(
        f"/api/v1/class-subject-requirements/{setup.source.requirement_ids[0]}",
        json={"lesson_pattern": None},
    )
    run = client.post(f"/api/v1/schedule-versions/{data['id']}/run-scheduler")

    assert patched.status_code == 200
    assert source_patch.status_code == 409
    assert run.status_code == 200, run.json()
    assert client.get(f"/api/v1/schedule-versions/{data['id']}").json()["status"] == "AUTO"


def test_copy_settings_of_a_working_copy_returns_409(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)
    working_copy = client.post(f"/api/v1/schedule-versions/{setup.source.version_id}/edit").json()

    response = _copy_settings(client, working_copy["id"])

    assert response.status_code == 409
    assert response.json()["detail"] == "編輯中的課表不能複製，請先儲存課表"


def test_copy_settings_missing_source_returns_404(client: TestClient) -> None:
    assert _copy_settings(client, 999999).status_code == 404


# --- Permissions ---


def test_copy_unauthenticated_returns_401(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    setup = _build_copy_setup(db_session)

    assert _copy(unauthenticated_client, setup.source.version_id).status_code == 401
    assert _copy_settings(unauthenticated_client, setup.source.version_id).status_code == 401


def test_copy_as_teacher_returns_403(teacher_client: TestClient, db_session: Session) -> None:
    setup = _build_copy_setup(db_session)
    before = _row_counts(db_session)

    assert _copy(teacher_client, setup.source.version_id).status_code == 403
    assert _copy_settings(teacher_client, setup.source.version_id).status_code == 403
    assert _row_counts(db_session) == before
