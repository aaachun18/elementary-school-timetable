import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class, Grade
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherAvailability, TeacherSubject
from app.models.time_slot import TimeSlot
from tests.test_move_swap_lessons import Timetable, _build_timetable, _move, _ok, _swap

# Task 83: GET /api/v1/schedule-versions/{id}/move-candidates/{schedule_id}
# -- for one lesson, the version's check after moving it to every time slot
# (and after every possible swap there), computed in memory without
# writing. Test data is written straight to the database through
# db_session.

URL = "/api/v1/schedule-versions"


# --- Helpers ---


def _candidates(client: TestClient, version_id: int, schedule_id: int) -> Any:
    return client.get(f"{URL}/{version_id}/move-candidates/{schedule_id}")


def _by_slot(data: dict) -> dict[int, dict]:
    return {candidate["time_slot_id"]: candidate for candidate in data["candidates"]}


def _types(check: dict) -> set[str]:
    return {violation["type"] for violation in check["violations"]}


def _new_types(data: dict, check: dict) -> set[str]:
    return _types(check) - _types(data["baseline"])


def _rich_timetable(db: Session) -> tuple[Timetable, TimeSlot]:
    """_build_timetable() plus: a non-teaching slot, teacher t2 unavailable
    at slot 4, c1 English's second lesson fixed to slot 1, and c2 English
    in room r1 -- so moves and swaps can hit H1/H2/H3/H4/H11 and the fixed
    slot check."""
    timetable = _build_timetable(db)
    lunch = TimeSlot(weekday=1, period=99, is_teaching_period=False, label="午休")
    db.add(lunch)
    db.add(TeacherAvailability(teacher_id=timetable.t2.id, time_slot_id=timetable.slot(4)))
    lesson = db.get(Lesson, timetable.c1_english[1].lesson_id)
    assert lesson is not None
    lesson.fixed_time_slot_id = timetable.slot(1)
    timetable.c2_english.room_id = timetable.r1.id
    db.commit()
    return timetable, lunch


def _all_rows(db: Session, version_id: int) -> list[Schedule]:
    db.expire_all()
    return list(
        db.scalars(
            select(Schedule).where(Schedule.schedule_version_id == version_id).order_by(Schedule.id)
        ).all()
    )


def _snapshot(db: Session) -> list[tuple[object, ...]]:
    db.expire_all()
    snapshot: list[tuple[object, ...]] = []
    for model in (
        ScheduleVersion,
        Schedule,
        Lesson,
        ClassSubjectRequirement,
        TimeSlot,
        Room,
        Teacher,
        TeacherAvailability,
        TeacherSubject,
        Class,
    ):
        columns = list(model.__table__.columns.keys())
        for row in db.scalars(select(model).order_by(model.id)).all():  # type: ignore[attr-defined]
            snapshot.append((model.__name__, *(getattr(row, c) for c in columns)))
    return snapshot


# --- Consistency with move-lesson / swap-lessons (dry_run) ---


def test_every_candidate_matches_move_and_swap_dry_runs(
    client: TestClient, db_session: Session
) -> None:
    timetable, _ = _rich_timetable(db_session)
    version_id = timetable.version.id
    compared_moves = compared_swaps = 0

    for row in _all_rows(db_session, version_id):
        data = _ok(_candidates(client, version_id, row.id))
        assert data["baseline"] == _ok(client.get(f"{URL}/{version_id}/check"))
        for candidate in data["candidates"]:
            if candidate["available"]:
                preview = _ok(
                    _move(client, version_id, row.id, candidate["time_slot_id"], dry_run=True)
                )
                assert candidate["move"] == preview["check"], (row.id, candidate["time_slot_id"])
                compared_moves += 1
            for swap in candidate["swaps"]:
                preview = _ok(
                    _swap(client, version_id, row.id, swap["swap_with_schedule_id"], dry_run=True)
                )
                assert swap["check"] == preview["check"], (row.id, swap["swap_with_schedule_id"])
                compared_swaps += 1

    # 4 rows x (7 slots - current - lunch); every row has swap partners.
    assert compared_moves == 4 * 5
    assert compared_swaps > 0


# --- Availability ---


def test_current_and_non_teaching_slots_are_not_move_targets(
    client: TestClient, db_session: Session
) -> None:
    timetable, lunch = _rich_timetable(db_session)
    row = timetable.c1_science  # slot 2

    data = _ok(_candidates(client, timetable.version.id, row.id))

    slots = _by_slot(data)
    assert data["schedule_id"] == row.id
    assert data["current_time_slot_id"] == timetable.slot(2)
    assert len(slots) == 7  # every time slot, one entry each
    assert slots[timetable.slot(2)]["available"] is False
    assert slots[timetable.slot(2)]["unavailable_reason"] == "CURRENT_SLOT"
    assert slots[timetable.slot(2)]["move"] is None
    assert slots[timetable.slot(2)]["swaps"] == []
    assert slots[lunch.id]["available"] is False
    assert slots[lunch.id]["unavailable_reason"] == "NON_TEACHING_SLOT"
    assert slots[lunch.id]["move"] is None
    for index in (0, 1, 3, 4, 5):
        candidate = slots[timetable.slot(index)]
        assert candidate["available"] is True
        assert candidate["unavailable_reason"] is None
        assert candidate["move"] is not None


# --- What the candidates say ---


def test_candidates_mark_conflicts_and_clean_slots(
    client: TestClient, db_session: Session
) -> None:
    timetable, _ = _rich_timetable(db_session)
    version_id = timetable.version.id

    # c2 English (teacher t1, slot 3): t1 teaches c1 English at slots 0, 1.
    c2 = _ok(_candidates(client, version_id, timetable.c2_english.id))
    c2_slots = _by_slot(c2)
    assert "H1_TEACHER_CONFLICT" in _new_types(c2, c2_slots[timetable.slot(0)]["move"])
    assert _new_types(c2, c2_slots[timetable.slot(5)]["move"]) == set()

    # c1 Science (teacher t2, slot 2): class c1 has English at 0; t2 is
    # unavailable at 4; slot 5 is free for both.
    science = _ok(_candidates(client, version_id, timetable.c1_science.id))
    slots = _by_slot(science)
    assert "H2_CLASS_CONFLICT" in _new_types(science, slots[timetable.slot(0)]["move"])
    assert _new_types(science, slots[timetable.slot(4)]["move"]) == {"H4_TEACHER_AVAILABILITY"}
    assert slots[timetable.slot(5)]["move"] == science["baseline"]
    assert science["baseline"]["is_valid"] is True


def test_swaps_list_only_lessons_sharing_class_teacher_or_room(
    client: TestClient, db_session: Session
) -> None:
    timetable, _ = _rich_timetable(db_session)
    version_id = timetable.version.id

    science = _by_slot(_ok(_candidates(client, version_id, timetable.c1_science.id)))
    # Same class (c1) at slots 0 and 1; c2 English at 3 shares nothing with
    # c1 Science (other class, teacher t1 vs t2, no room).
    assert [s["swap_with_schedule_id"] for s in science[timetable.slot(0)]["swaps"]] == [
        timetable.c1_english[0].id
    ]
    assert [s["swap_with_schedule_id"] for s in science[timetable.slot(1)]["swaps"]] == [
        timetable.c1_english[1].id
    ]
    assert science[timetable.slot(3)]["swaps"] == []
    assert science[timetable.slot(5)]["swaps"] == []

    # c2 English (t1, room r1): c1 English rows share teacher t1, and the one
    # at slot 0 also shares room r1 -- both listed once.
    c2 = _by_slot(_ok(_candidates(client, version_id, timetable.c2_english.id)))
    assert [s["swap_with_schedule_id"] for s in c2[timetable.slot(0)]["swaps"]] == [
        timetable.c1_english[0].id
    ]
    assert [s["swap_with_schedule_id"] for s in c2[timetable.slot(1)]["swaps"]] == [
        timetable.c1_english[1].id
    ]
    # Swapping c1 English #2 off its fixed slot 1 reports the fixed slot.
    swap_check = c2[timetable.slot(1)]["swaps"][0]["check"]
    assert "FIXED_TIME_SLOT_MISMATCH" in _types(swap_check)


# --- Writes nothing ---


def test_candidates_write_nothing(client: TestClient, db_session: Session) -> None:
    timetable, _ = _rich_timetable(db_session)
    before = _snapshot(db_session)

    for row in _all_rows(db_session, timetable.version.id):
        _ok(_candidates(client, timetable.version.id, row.id))

    assert _snapshot(db_session) == before


# --- Refusals ---


def test_teacher_gets_403(teacher_client: TestClient, db_session: Session) -> None:
    timetable = _build_timetable(db_session)

    response = _candidates(teacher_client, timetable.version.id, timetable.c1_science.id)

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("PUBLISHED", "已發布版本不可修改，請建立新草稿版本"),
        ("ARCHIVED", "已封存的課表無法修改，請先複製成新草稿"),
    ],
)
def test_locked_version_returns_409(
    client: TestClient, db_session: Session, status: str, message: str
) -> None:
    timetable = _build_timetable(db_session)
    timetable.version.status = status
    db_session.commit()

    response = _candidates(client, timetable.version.id, timetable.c1_science.id)

    assert response.status_code == 409
    assert response.json()["detail"] == message


def test_missing_version_or_row_returns_404(client: TestClient, db_session: Session) -> None:
    timetable = _build_timetable(db_session)
    other_version = timetable.builder.version(number=2)
    foreign_row = Schedule(
        schedule_version_id=other_version.id,
        lesson_id=timetable.c1_science.lesson_id,
        teacher_id=timetable.t2.id,
        time_slot_id=timetable.slot(2),
    )
    db_session.add(foreign_row)
    db_session.commit()

    missing_version = _candidates(client, 999_999, timetable.c1_science.id)
    missing_row = _candidates(client, timetable.version.id, 999_999)
    row_of_other_version = _candidates(client, timetable.version.id, foreign_row.id)

    assert missing_version.status_code == 404
    assert missing_version.json()["detail"] == "ScheduleVersion not found"
    for response in (missing_row, row_of_other_version):
        assert response.status_code == 404
        assert response.json()["detail"] == "Schedule not found"


# --- Performance (loose limits: guards against regressions only) ---


def _build_scaled_version(db: Session, *, classes: int, lessons_per_class: int) -> tuple[int, int]:
    """A DRAFT version with classes x lessons_per_class rows over a 5-day,
    10-period week (period 0 and 5 non-teaching, like the demo data).
    Returns (version id, one schedule id)."""
    year = AcademicYear(year=7000 + classes, is_active=True)
    db.add(year)
    db.flush()
    semester = Semester(academic_year_id=year.id, number=1, is_active=True)
    grade = Grade(name=f"Grade scale {classes}", level=7000 + classes)
    db.add_all([semester, grade])
    db.flush()
    slots = [
        TimeSlot(weekday=weekday, period=period, is_teaching_period=period not in (0, 5))
        for weekday in range(1, 6)
        for period in range(0, 10)
    ]
    db.add_all(slots)
    teaching = [slot for slot in slots if slot.is_teaching_period]
    subjects = [Subject(name=f"Scale subject {i}", is_active=True) for i in range(lessons_per_class)]
    teachers = [
        Teacher(name=f"Scale teacher {i}", is_active=True, min_weekly_periods=0, max_weekly_periods=40)
        for i in range(lessons_per_class)
    ]
    db.add_all([*subjects, *teachers])
    db.flush()
    db.add_all(
        [TeacherSubject(teacher_id=t.id, subject_id=s.id) for t, s in zip(teachers, subjects)]
    )
    version = ScheduleVersion(semester_id=semester.id, version_number=1, status="DRAFT")
    db.add(version)
    db.flush()
    rows: list[Schedule] = []
    for c in range(classes):
        class_ = Class(name=f"Scale class {c}", grade_id=grade.id, is_active=True)
        db.add(class_)
        db.flush()
        for i in range(lessons_per_class):
            requirement = ClassSubjectRequirement(
                semester_id=semester.id,
                class_id=class_.id,
                subject_id=subjects[i].id,
                weekly_periods=1,
            )
            db.add(requirement)
            db.flush()
            lesson = Lesson(class_subject_requirement_id=requirement.id, sequence_number=1)
            db.add(lesson)
            db.flush()
            # Teacher i teaches subject i in every class: spread over slots.
            slot = teaching[(c + i * classes) % len(teaching)]
            rows.append(
                Schedule(
                    schedule_version_id=version.id,
                    lesson_id=lesson.id,
                    teacher_id=teachers[i].id,
                    time_slot_id=slot.id,
                )
            )
    db.add_all(rows)
    db.commit()
    return version.id, rows[0].id


@pytest.mark.parametrize(
    ("classes", "lessons_per_class", "limit_seconds"),
    [(6, 5, 5.0), (30, 10, 30.0)],  # ~demo size (30 rows), scaled (300 rows)
)
def test_candidates_response_time(
    client: TestClient,
    db_session: Session,
    classes: int,
    lessons_per_class: int,
    limit_seconds: float,
) -> None:
    version_id, schedule_id = _build_scaled_version(
        db_session, classes=classes, lessons_per_class=lessons_per_class
    )

    started = time.perf_counter()
    data = _ok(_candidates(client, version_id, schedule_id))
    elapsed = time.perf_counter() - started

    print(f"\n[move-candidates] {classes * lessons_per_class} rows, 50 slots: {elapsed:.3f}s")
    assert len(data["candidates"]) == 50
    assert elapsed < limit_seconds
