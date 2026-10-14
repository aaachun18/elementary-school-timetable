import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.time_slot import TimeSlot
from tests.test_move_swap_lessons import _build_timetable, _get, _move, _ok, _swap
from tests.test_schedule_check import (
    _add_schedule,
    _build_setup,
    _check,
    _violations_of_type,
)
from tests.test_schedule_copy import _build_copy_setup, _copy_cross

# Task 66: GET /api/v1/schedule-versions/{id}/check reports a Schedule row
# whose Lesson is pinned (Lesson.fixed_time_slot_id) but sits in another
# time slot as FIXED_TIME_SLOT_MISMATCH.

FIXED = "FIXED_TIME_SLOT_MISMATCH"


def _add_extra_slot(db: Session) -> int:
    slot = TimeSlot(weekday=2, period=1, is_teaching_period=True)
    db.add(slot)
    db.commit()
    return slot.id


def _fix(db: Session, lesson_id: int, time_slot_id: int) -> None:
    lesson = db.get(Lesson, lesson_id)
    assert lesson is not None
    lesson.fixed_time_slot_id = time_slot_id
    db.commit()


def test_fixed_lesson_placed_by_run_scheduler_is_valid(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_setup(db_session)
    _fix(db_session, setup.lesson_ids[0], setup.time_slot_ids[1])

    run_response = client.post(
        f"/api/v1/schedule-versions/{setup.version_id}/run-scheduler"
    )
    assert run_response.status_code == 200

    data = _check(client, setup.version_id)
    assert data["is_valid"] is True
    assert _violations_of_type(data, FIXED) == []


def test_moving_fixed_lesson_away_and_back(client: TestClient, db_session: Session) -> None:
    tt = _build_timetable(db_session)
    science = tt.c1_science
    _fix(db_session, science.lesson_id, tt.slot(2))

    moved = _ok(_move(client, tt.version.id, science.id, tt.slot(5)))

    violations = [v for v in moved["check"]["violations"] if v["type"] == FIXED]
    assert len(violations) == 1
    violation = violations[0]
    assert violation["severity"] == "ERROR"
    assert violation["lesson_id"] == science.lesson_id
    assert violation["time_slot_id"] == tt.slot(5)
    assert violation["teacher_id"] == tt.t2.id
    assert violation["class_id"] == tt.c1.id
    assert violation["subject_id"] == tt.science.id
    assert violation["room_id"] is None
    assert violation["class_subject_requirement_id"] is not None
    assert str(tt.slot(2)) in violation["message"]
    assert str(tt.slot(5)) in violation["message"]
    assert violation["suggested_action"]
    # The same result from the stand-alone check endpoint.
    assert _violations_of_type(_check(client, tt.version.id), FIXED) == violations

    moved_back = _ok(_move(client, tt.version.id, science.id, tt.slot(2)))

    assert moved_back["check"]["is_valid"] is True
    db_session.expire_all()
    assert db_session.get(Lesson, science.lesson_id).fixed_time_slot_id == tt.slot(2)


def test_moving_unfixed_lesson_reports_no_mismatch(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)

    data = _ok(_move(client, tt.version.id, tt.c1_science.id, tt.slot(5)))

    assert data["check"]["is_valid"] is True
    assert [v for v in data["check"]["violations"] if v["type"] == FIXED] == []


def test_swapping_two_fixed_lessons_reports_both(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)
    english, science = tt.c1_english[0], tt.c1_science
    _fix(db_session, english.lesson_id, tt.slot(0))
    _fix(db_session, science.lesson_id, tt.slot(2))

    data = _ok(_swap(client, tt.version.id, english.id, science.id))

    violations = [v for v in data["check"]["violations"] if v["type"] == FIXED]
    assert {(v["lesson_id"], v["time_slot_id"]) for v in violations} == {
        (english.lesson_id, tt.slot(2)),
        (science.lesson_id, tt.slot(0)),
    }
    assert _get(db_session, english.id).time_slot_id == tt.slot(2)


def test_copy_keeps_fixed_time_slot_mismatch(
    client: TestClient, db_session: Session
) -> None:
    # _build_copy_setup pins lesson 1 to slot 1; move its row to an unused
    # slot so the source has exactly this one mismatch.
    setup = _build_copy_setup(db_session)
    source = setup.source
    extra_slot_id = _add_extra_slot(db_session)
    row = db_session.scalars(
        select(Schedule).where(
            Schedule.schedule_version_id == source.version_id,
            Schedule.lesson_id == source.lesson_ids[1],
        )
    ).one()
    row.time_slot_id = extra_slot_id
    db_session.commit()
    source_violations = _violations_of_type(_check(client, source.version_id), FIXED)
    assert [v["time_slot_id"] for v in source_violations] == [extra_slot_id]

    copy = _copy_cross(client, setup)

    copy_violations = _violations_of_type(_check(client, copy["id"]), FIXED)
    assert [v["time_slot_id"] for v in copy_violations] == [extra_slot_id]
    # The copy's Lesson is a new row, pinned to the same slot.
    assert copy_violations[0]["lesson_id"] != source_violations[0]["lesson_id"]
    copied_lesson = db_session.get(Lesson, copy_violations[0]["lesson_id"])
    assert copied_lesson is not None
    assert copied_lesson.fixed_time_slot_id == source.time_slot_ids[1]


def test_row_without_time_slot_reports_only_incomplete_row(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_setup(db_session)
    _fix(db_session, setup.lesson_ids[1], setup.time_slot_ids[1])
    _add_schedule(db_session, setup, setup.lesson_ids[0], setup.time_slot_ids[0])
    db_session.add(
        Schedule(
            schedule_version_id=setup.version_id,
            lesson_id=setup.lesson_ids[1],
            teacher_id=setup.teacher_id,
            time_slot_id=None,
            room_id=None,
        )
    )
    db_session.commit()

    data = _check(client, setup.version_id)

    assert len(_violations_of_type(data, "INCOMPLETE_SCHEDULE_ROW")) == 1
    assert _violations_of_type(data, FIXED) == []


@pytest.mark.parametrize("status", ["PUBLISHED", "ARCHIVED"])
def test_locked_version_reports_mismatch(
    client: TestClient, db_session: Session, status: str
) -> None:
    setup = _build_setup(db_session)
    # Otherwise valid (one teacher, two classes, two different slots), but
    # lesson 0 is pinned to slot 1 while stored in slot 0.
    _fix(db_session, setup.lesson_ids[0], setup.time_slot_ids[1])
    _add_schedule(db_session, setup, setup.lesson_ids[0], setup.time_slot_ids[0])
    _add_schedule(db_session, setup, setup.lesson_ids[1], setup.time_slot_ids[1])
    version = db_session.get(ScheduleVersion, setup.version_id)
    assert version is not None
    version.status = status
    db_session.commit()

    data = _check(client, setup.version_id)

    assert data["is_valid"] is False
    assert [v["type"] for v in data["violations"]] == [FIXED]
    assert data["violations"][0]["lesson_id"] == setup.lesson_ids[0]
    assert data["violations"][0]["time_slot_id"] == setup.time_slot_ids[0]
