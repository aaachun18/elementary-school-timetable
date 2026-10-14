from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class, Grade
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherAvailability, TeacherSubject
from app.models.time_slot import TimeSlot

# Task 61: GET /api/v1/schedule-versions/{id}/check -- read-only Hard
# Constraint check of a version's CURRENT Schedule rows. Test data is
# written straight to the database through db_session (the same session
# the `client` fixture's requests use), so each test can build exactly the
# broken timetable it needs without going through the scheduler.


@dataclass
class CheckSetup:
    """Two classes, each with one 1-period requirement of the same subject
    (so two Lessons that do NOT share a class -- putting both in one slot
    is an H1 teacher conflict without also being an H2 class conflict),
    one qualified teacher, and two teaching time slots."""

    semester_id: int
    version_id: int
    teacher_id: int
    time_slot_ids: list[int]
    requirement_ids: list[int]
    lesson_ids: list[int]


def _build_setup(db: Session, year: int = 4001) -> CheckSetup:
    academic_year = AcademicYear(year=year, is_active=True)
    db.add(academic_year)
    db.flush()
    semester = Semester(academic_year_id=academic_year.id, number=1, is_active=True)
    grade = Grade(name=f"Grade {year}", level=year)
    subject = Subject(name=f"Subject {year}", is_active=True)
    teacher = Teacher(
        name=f"Teacher {year}", is_active=True, min_weekly_periods=0, max_weekly_periods=20
    )
    db.add_all([semester, grade, subject, teacher])
    db.flush()

    classes = [
        Class(grade_id=grade.id, name=f"Class {year}-{index}", is_active=True)
        for index in (1, 2)
    ]
    time_slots = [
        TimeSlot(weekday=1, period=period, is_teaching_period=True) for period in (1, 2)
    ]
    db.add_all([*classes, *time_slots, TeacherSubject(teacher_id=teacher.id, subject_id=subject.id)])
    db.flush()

    requirements = [
        ClassSubjectRequirement(
            semester_id=semester.id,
            class_id=class_.id,
            subject_id=subject.id,
            weekly_periods=1,
        )
        for class_ in classes
    ]
    version = ScheduleVersion(semester_id=semester.id, version_number=1, status="DRAFT")
    db.add_all([*requirements, version])
    db.flush()

    lessons = [
        Lesson(class_subject_requirement_id=requirement.id, sequence_number=1)
        for requirement in requirements
    ]
    db.add_all(lessons)
    db.commit()

    return CheckSetup(
        semester_id=semester.id,
        version_id=version.id,
        teacher_id=teacher.id,
        time_slot_ids=[time_slot.id for time_slot in time_slots],
        requirement_ids=[requirement.id for requirement in requirements],
        lesson_ids=[lesson.id for lesson in lessons],
    )


def _add_schedule(
    db: Session, setup: CheckSetup, lesson_id: int, time_slot_id: int
) -> None:
    db.add(
        Schedule(
            schedule_version_id=setup.version_id,
            lesson_id=lesson_id,
            teacher_id=setup.teacher_id,
            time_slot_id=time_slot_id,
            room_id=None,
        )
    )
    db.commit()


def _place_both_lessons_validly(db: Session, setup: CheckSetup) -> None:
    for lesson_id, time_slot_id in zip(setup.lesson_ids, setup.time_slot_ids):
        _add_schedule(db, setup, lesson_id, time_slot_id)


def _place_both_lessons_in_same_slot(db: Session, setup: CheckSetup) -> None:
    for lesson_id in setup.lesson_ids:
        _add_schedule(db, setup, lesson_id, setup.time_slot_ids[0])


def _check(client: TestClient, version_id: int) -> dict:
    response = client.get(f"/api/v1/schedule-versions/{version_id}/check")
    assert response.status_code == 200
    data: dict = response.json()
    return data


def _violations_of_type(data: dict, violation_type: str) -> list[dict]:
    return [v for v in data["violations"] if v["type"] == violation_type]


# --- Valid timetable ---


def test_check_schedule_produced_by_run_scheduler_is_valid(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_setup(db_session)
    run_response = client.post(
        f"/api/v1/schedule-versions/{setup.version_id}/run-scheduler"
    )
    assert run_response.status_code == 200

    data = _check(client, setup.version_id)

    assert data == {
        "schedule_version_id": setup.version_id,
        "is_valid": True,
        "violation_count": 0,
        "violations": [],
    }


# --- Each kind of violation ---


def test_check_reports_teacher_conflict(client: TestClient, db_session: Session) -> None:
    setup = _build_setup(db_session)
    _place_both_lessons_in_same_slot(db_session, setup)

    data = _check(client, setup.version_id)

    assert data["is_valid"] is False
    assert data["violation_count"] == len(data["violations"])
    h1 = _violations_of_type(data, "H1_TEACHER_CONFLICT")
    assert sorted(v["lesson_id"] for v in h1) == sorted(setup.lesson_ids)
    for violation in h1:
        assert violation["teacher_id"] == setup.teacher_id
        assert violation["time_slot_id"] == setup.time_slot_ids[0]
        assert violation["severity"] == "ERROR"
    # Different classes: a teacher conflict only, not a class conflict.
    assert _violations_of_type(data, "H2_CLASS_CONFLICT") == []


def test_check_reports_inactive_teacher(client: TestClient, db_session: Session) -> None:
    setup = _build_setup(db_session)
    _place_both_lessons_validly(db_session, setup)
    teacher = db_session.get(Teacher, setup.teacher_id)
    assert teacher is not None
    teacher.is_active = False
    db_session.commit()

    data = _check(client, setup.version_id)

    assert data["is_valid"] is False
    h12 = _violations_of_type(data, "H12_ACTIVE_STATUS")
    assert sorted(v["lesson_id"] for v in h12) == sorted(setup.lesson_ids)
    assert all(v["teacher_id"] == setup.teacher_id for v in h12)


def test_check_reports_lesson_without_schedule_row(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_setup(db_session)
    # Only the first lesson is placed; the second has no Schedule row.
    _add_schedule(db_session, setup, setup.lesson_ids[0], setup.time_slot_ids[0])

    data = _check(client, setup.version_id)

    assert data["is_valid"] is False
    h7 = _violations_of_type(data, "H7_WEEKLY_PERIODS")
    assert [v["class_subject_requirement_id"] for v in h7] == [setup.requirement_ids[1]]


def test_check_version_with_no_schedule_rows_reports_every_requirement(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_setup(db_session)

    data = _check(client, setup.version_id)

    # Not special-cased as "nothing to check": H7 reports both requirements.
    assert data["is_valid"] is False
    assert data["violation_count"] == 2
    assert sorted(
        v["class_subject_requirement_id"]
        for v in _violations_of_type(data, "H7_WEEKLY_PERIODS")
    ) == sorted(setup.requirement_ids)


def test_check_reports_teacher_unavailable_slot(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_setup(db_session)
    _place_both_lessons_validly(db_session, setup)
    unavailable_slot_id = setup.time_slot_ids[1]
    db_session.add(
        TeacherAvailability(teacher_id=setup.teacher_id, time_slot_id=unavailable_slot_id)
    )
    db_session.commit()

    data = _check(client, setup.version_id)

    assert data["is_valid"] is False
    h4 = _violations_of_type(data, "H4_TEACHER_AVAILABILITY")
    assert len(h4) == 1
    assert h4[0]["lesson_id"] == setup.lesson_ids[1]
    assert h4[0]["teacher_id"] == setup.teacher_id
    assert h4[0]["time_slot_id"] == unavailable_slot_id


def test_check_reports_schedule_row_without_time_slot(
    client: TestClient, db_session: Session
) -> None:
    # Task 62: such a row used to be skipped by every rule (all of them need
    # a time slot), so the version came back as valid.
    setup = _build_setup(db_session)
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

    assert data["is_valid"] is False
    incomplete = _violations_of_type(data, "INCOMPLETE_SCHEDULE_ROW")
    assert len(incomplete) == 1
    assert incomplete[0]["lesson_id"] == setup.lesson_ids[1]
    assert incomplete[0]["teacher_id"] == setup.teacher_id
    assert incomplete[0]["time_slot_id"] is None
    assert incomplete[0]["severity"] == "ERROR"


def test_check_reports_schedule_row_without_teacher(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_setup(db_session)
    _add_schedule(db_session, setup, setup.lesson_ids[0], setup.time_slot_ids[0])
    db_session.add(
        Schedule(
            schedule_version_id=setup.version_id,
            lesson_id=setup.lesson_ids[1],
            teacher_id=None,
            time_slot_id=setup.time_slot_ids[1],
            room_id=None,
        )
    )
    db_session.commit()

    data = _check(client, setup.version_id)

    assert data["is_valid"] is False
    incomplete = _violations_of_type(data, "INCOMPLETE_SCHEDULE_ROW")
    assert len(incomplete) == 1
    assert incomplete[0]["lesson_id"] == setup.lesson_ids[1]
    assert incomplete[0]["teacher_id"] is None
    assert incomplete[0]["time_slot_id"] == setup.time_slot_ids[1]


# --- PUBLISHED versions ---


def test_check_published_version_same_result_as_draft(
    client: TestClient, db_session: Session
) -> None:
    setup = _build_setup(db_session)
    _place_both_lessons_in_same_slot(db_session, setup)
    draft_data = _check(client, setup.version_id)

    version = db_session.get(ScheduleVersion, setup.version_id)
    assert version is not None
    version.status = "PUBLISHED"
    db_session.commit()

    published_data = _check(client, setup.version_id)

    assert published_data == draft_data
    assert published_data["is_valid"] is False


# --- Read-only and deterministic ---


def _snapshot(db: Session) -> list[tuple[object, ...]]:
    db.expire_all()
    schedules = db.scalars(select(Schedule).order_by(Schedule.id)).all()
    return [
        (
            schedule.id,
            schedule.schedule_version_id,
            schedule.lesson_id,
            schedule.teacher_id,
            schedule.time_slot_id,
            schedule.room_id,
            schedule.updated_at,
        )
        for schedule in schedules
    ]


def test_check_does_not_modify_database(client: TestClient, db_session: Session) -> None:
    setup = _build_setup(db_session)
    _place_both_lessons_in_same_slot(db_session, setup)
    before = _snapshot(db_session)
    lesson_count_before = len(db_session.scalars(select(Lesson)).all())
    version_status_before = db_session.get(ScheduleVersion, setup.version_id).status

    _check(client, setup.version_id)

    assert _snapshot(db_session) == before
    assert len(before) == 2
    assert len(db_session.scalars(select(Lesson)).all()) == lesson_count_before
    assert db_session.get(ScheduleVersion, setup.version_id).status == version_status_before


def test_check_result_order_is_stable(client: TestClient, db_session: Session) -> None:
    setup = _build_setup(db_session)
    # Several violation types at once: H1 (same slot) + H12 (inactive teacher).
    _place_both_lessons_in_same_slot(db_session, setup)
    teacher = db_session.get(Teacher, setup.teacher_id)
    assert teacher is not None
    teacher.is_active = False
    db_session.commit()

    first = _check(client, setup.version_id)
    second = _check(client, setup.version_id)

    assert first == second
    keys = [
        (v["type"], v["lesson_id"] or 0, v["time_slot_id"] or 0)
        for v in first["violations"]
    ]
    assert keys == sorted(keys)


# --- Errors and permissions ---


def test_check_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/schedule-versions/999999/check")

    assert response.status_code == 404
    assert response.json()["detail"] == "ScheduleVersion not found"


def test_check_unauthenticated_returns_401(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    setup = _build_setup(db_session)

    response = unauthenticated_client.get(
        f"/api/v1/schedule-versions/{setup.version_id}/check"
    )

    assert response.status_code == 401


@pytest.mark.parametrize("status", ["DRAFT", "PUBLISHED", "ARCHIVED"])
def test_check_is_admin_only(
    teacher_client: TestClient, db_session: Session, status: str
) -> None:
    # Task 72 (was: a TEACHER could check a PUBLISHED version): the check
    # is an administrative tool -- 403 for a TEACHER whatever the status.
    setup = _build_setup(db_session)
    _place_both_lessons_validly(db_session, setup)
    version = db_session.get(ScheduleVersion, setup.version_id)
    assert version is not None
    version.status = status
    db_session.commit()

    response = teacher_client.get(f"/api/v1/schedule-versions/{setup.version_id}/check")

    assert response.status_code == 403
    assert response.json()["detail"] == "This action requires ADMIN role"


def test_check_missing_version_is_403_for_teacher(teacher_client: TestClient) -> None:
    # The role check comes first, so a TEACHER can't probe which ids exist.
    response = teacher_client.get("/api/v1/schedule-versions/999999/check")

    assert response.status_code == 403
