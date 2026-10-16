"""Task 88: TEACHER_MIN_WORKLOAD -- a teacher scheduled for fewer periods
than their min_weekly_periods is reported by the schedule check as a
WARNING. It never blocks anything: the timetable stays is_valid, and
run-scheduler, publishing and moving all go through.

Test data is written straight to the database through db_session.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.teacher import Teacher
from tests.test_move_swap_lessons import _build_timetable, _move, _ok
from tests.test_reassign_teacher import Builder

URL = "/api/v1/schedule-versions"
MIN_TYPE = "TEACHER_MIN_WORKLOAD"


def _check(client: TestClient, version_id: int) -> dict:
    return _ok(client.get(f"{URL}/{version_id}/check"))


def _min_violations(check: dict) -> list[dict]:
    return [v for v in check["violations"] if v["type"] == MIN_TYPE]


def test_teacher_below_minimum_gets_a_warning(client: TestClient, db_session: Session) -> None:
    # t1 teaches 3 lessons (c1 English x2, c2 English), t2 one (c1 Science).
    timetable = _build_timetable(db_session)
    timetable.t1.min_weekly_periods = 4
    db_session.commit()

    check = _check(client, timetable.version.id)

    assert check["is_valid"] is True
    assert check["violation_count"] == 1
    [violation] = _min_violations(check)
    assert violation["severity"] == "WARNING"
    assert violation["teacher_id"] == timetable.t1.id
    assert violation["lesson_id"] is None
    assert violation["schedule_id"] is None
    assert violation["identity_key"] == f"{MIN_TYPE}:{timetable.t1.id}"
    assert "3" in violation["message"] and "4" in violation["message"]


def test_teacher_at_minimum_is_not_reported(client: TestClient, db_session: Session) -> None:
    timetable = _build_timetable(db_session)
    timetable.t1.min_weekly_periods = 3
    timetable.t2.min_weekly_periods = 1
    db_session.commit()

    assert _check(client, timetable.version.id)["violations"] == []


def test_teacher_with_no_lessons_counts_as_zero(client: TestClient, db_session: Session) -> None:
    timetable = _build_timetable(db_session)
    idle = timetable.builder.teacher("三號老師", [timetable.english])
    idle.min_weekly_periods = 2
    db_session.commit()

    [violation] = _min_violations(_check(client, timetable.version.id))

    assert violation["teacher_id"] == idle.id


def test_inactive_teacher_is_not_reported(client: TestClient, db_session: Session) -> None:
    timetable = _build_timetable(db_session)
    idle = timetable.builder.teacher("停用老師", [timetable.english])
    idle.min_weekly_periods = 2
    idle.is_active = False
    db_session.commit()

    assert _min_violations(_check(client, timetable.version.id)) == []


def test_warning_alongside_errors_keeps_both(client: TestClient, db_session: Session) -> None:
    """is_valid is decided by the ERRORs alone."""
    timetable = _build_timetable(db_session)
    timetable.t2.min_weekly_periods = 5
    db_session.commit()
    # c2 English (t1) into c1 English's slot 0: H1 teacher conflict.
    preview = _ok(
        _move(client, timetable.version.id, timetable.c2_english.id, timetable.slot(0), dry_run=True)
    )["check"]

    assert preview["is_valid"] is False
    assert {v["type"] for v in preview["violations"]} == {"H1_TEACHER_CONFLICT", MIN_TYPE}


def test_moving_is_not_blocked_by_the_warning(client: TestClient, db_session: Session) -> None:
    timetable = _build_timetable(db_session)
    timetable.t2.min_weekly_periods = 5
    db_session.commit()

    result = _ok(_move(client, timetable.version.id, timetable.c1_science.id, timetable.slot(4)))

    assert result["changes"] != []
    assert result["check"]["is_valid"] is True
    assert [v["type"] for v in result["check"]["violations"]] == [MIN_TYPE]


def test_run_scheduler_and_publish_are_not_blocked(
    client: TestClient, db_session: Session
) -> None:
    builder = Builder(db_session, year=8802)
    english = builder.subject("英文")
    teacher = builder.teacher("一號老師", [english])
    teacher.min_weekly_periods = 10  # far more than the 2 periods below
    class_ = builder.class_("四年甲班")
    version = builder.version()
    requirement = ClassSubjectRequirement(
        semester_id=version.semester_id, class_id=class_.id, subject_id=english.id, weekly_periods=2
    )
    db_session.add(requirement)
    db_session.flush()
    db_session.add_all(
        [Lesson(class_subject_requirement_id=requirement.id, sequence_number=n) for n in (1, 2)]
    )
    db_session.commit()

    run = client.post(f"{URL}/{version.id}/run-scheduler")
    assert run.status_code == 200, run.json()
    assert run.json()["scheduled_count"] == 2

    check = _check(client, version.id)
    assert check["is_valid"] is True
    assert [v["teacher_id"] for v in _min_violations(check)] == [teacher.id]

    published = client.patch(f"{URL}/{version.id}", json={"status": "PUBLISHED"})
    assert published.status_code == 200, published.json()
    assert published.json()["status"] == "PUBLISHED"
    db_session.expire_all()
    assert db_session.get(Teacher, teacher.id).min_weekly_periods == 10  # type: ignore[union-attr]
