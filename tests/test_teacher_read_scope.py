from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from tests.test_reassign_teacher import Builder

# Task 72: what a TEACHER may read. Lessons and class-subject-requirements
# are only visible for semesters that currently have a PUBLISHED version
# (list = silent filter, single record = the usual 404); Schedule rows only
# for PUBLISHED versions; the check endpoint is ADMIN-only. ADMIN is
# unaffected. Test data is written straight to the database.


@dataclass
class ScopeWorld:
    """Three semesters, one course each:
    - published_semester: its version is PUBLISHED (plus a DRAFT copy of
      the same course's rows in a second version);
    - archived_semester: its only version is ARCHIVED;
    - draft_semester (another academic year): its only version is DRAFT."""

    published_semester: Semester
    archived_semester: Semester
    draft_semester: Semester
    published_version: ScheduleVersion
    draft_version_same_semester: ScheduleVersion
    archived_version: ScheduleVersion
    draft_version: ScheduleVersion
    published_requirement: ClassSubjectRequirement
    archived_requirement: ClassSubjectRequirement
    draft_requirement: ClassSubjectRequirement


def _set_status(db: Session, version: ScheduleVersion, status: str) -> None:
    version.status = status
    db.commit()


def _build_world(db: Session) -> ScopeWorld:
    builder = Builder(db)
    archived_semester = builder.semester_in_year(number=2)
    other_year = AcademicYear(year=6002, is_active=True)
    db.add(other_year)
    db.flush()
    draft_semester = Semester(academic_year_id=other_year.id, number=1, is_active=True)
    db.add(draft_semester)
    db.commit()

    english = builder.subject("英文")
    teacher = builder.teacher("老師", [english])
    class_ = builder.class_("一班")

    published_version = builder.version()
    published_requirement = builder.course(published_version, class_, english, teacher, [0, 1])
    draft_version_same_semester = builder.version(number=2)
    for schedule in db.scalars(
        select(Schedule).where(Schedule.schedule_version_id == published_version.id)
    ).all():
        db.add(
            Schedule(
                schedule_version_id=draft_version_same_semester.id,
                lesson_id=schedule.lesson_id,
                teacher_id=schedule.teacher_id,
                time_slot_id=schedule.time_slot_id,
                room_id=None,
            )
        )
    db.commit()
    _set_status(db, published_version, "PUBLISHED")

    archived_version = builder.version(semester=archived_semester)
    archived_requirement = builder.course(archived_version, class_, english, teacher, [2])
    _set_status(db, archived_version, "ARCHIVED")

    draft_version = builder.version(semester=draft_semester)
    draft_requirement = builder.course(draft_version, class_, english, teacher, [3])

    return ScopeWorld(
        published_semester=builder.semester,
        archived_semester=archived_semester,
        draft_semester=draft_semester,
        published_version=published_version,
        draft_version_same_semester=draft_version_same_semester,
        archived_version=archived_version,
        draft_version=draft_version,
        published_requirement=published_requirement,
        archived_requirement=archived_requirement,
        draft_requirement=draft_requirement,
    )


def _ids(response: Any) -> list[int]:
    assert response.status_code == 200, response.json()
    return [item["id"] for item in response.json()]


def _lesson_ids(db: Session, requirement: ClassSubjectRequirement) -> list[int]:
    return list(
        db.scalars(
            select(Lesson.id)
            .where(Lesson.class_subject_requirement_id == requirement.id)
            .order_by(Lesson.id)
        ).all()
    )


def _schedule_ids(db: Session, version: ScheduleVersion) -> list[int]:
    return list(
        db.scalars(
            select(Schedule.id)
            .where(Schedule.schedule_version_id == version.id)
            .order_by(Schedule.id)
        ).all()
    )


# --- Lessons ---


def test_teacher_lists_only_lessons_of_semesters_with_published_version(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)

    teacher_ids = _ids(teacher_client.get("/api/v1/lessons/"))
    admin_ids = _ids(client.get("/api/v1/lessons/"))

    assert teacher_ids == _lesson_ids(db_session, world.published_requirement)
    assert admin_ids == sorted(
        _lesson_ids(db_session, world.published_requirement)
        + _lesson_ids(db_session, world.archived_requirement)
        + _lesson_ids(db_session, world.draft_requirement)
    )


def test_teacher_lesson_semester_filter_respects_visibility(
    teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)

    def listed(semester: Semester) -> list[int]:
        return _ids(teacher_client.get("/api/v1/lessons/", params={"semester_id": semester.id}))

    assert listed(world.published_semester) == _lesson_ids(db_session, world.published_requirement)
    assert listed(world.archived_semester) == []
    assert listed(world.draft_semester) == []


def test_teacher_lesson_pages_join_up(teacher_client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)

    first = _ids(teacher_client.get("/api/v1/lessons/", params={"skip": 0, "limit": 1}))
    second = _ids(teacher_client.get("/api/v1/lessons/", params={"skip": 1, "limit": 1}))
    rest = _ids(teacher_client.get("/api/v1/lessons/", params={"skip": 2, "limit": 1}))

    assert first + second + rest == _lesson_ids(db_session, world.published_requirement)
    assert rest == []


def test_teacher_get_lesson_hidden_semester_is_404(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    visible_id = _lesson_ids(db_session, world.published_requirement)[0]

    assert teacher_client.get(f"/api/v1/lessons/{visible_id}").status_code == 200
    for requirement in (world.archived_requirement, world.draft_requirement):
        lesson_id = _lesson_ids(db_session, requirement)[0]
        response = teacher_client.get(f"/api/v1/lessons/{lesson_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Lesson not found"
        # ADMIN unaffected.
        assert client.get(f"/api/v1/lessons/{lesson_id}").status_code == 200


# --- Class-subject requirements ---


def test_teacher_lists_only_requirements_of_semesters_with_published_version(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    url = "/api/v1/class-subject-requirements/"

    assert _ids(teacher_client.get(url)) == [world.published_requirement.id]
    assert _ids(client.get(url)) == sorted(
        [
            world.published_requirement.id,
            world.archived_requirement.id,
            world.draft_requirement.id,
        ]
    )
    assert _ids(teacher_client.get(url, params={"semester_id": world.archived_semester.id})) == []
    assert _ids(
        teacher_client.get(url, params={"semester_id": world.published_semester.id})
    ) == [world.published_requirement.id]


def test_teacher_get_requirement_hidden_semester_is_404(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    url = "/api/v1/class-subject-requirements"

    assert teacher_client.get(f"{url}/{world.published_requirement.id}").status_code == 200
    for requirement in (world.archived_requirement, world.draft_requirement):
        response = teacher_client.get(f"{url}/{requirement.id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "ClassSubjectRequirement not found"
        assert client.get(f"{url}/{requirement.id}").status_code == 200


def test_unpublishing_hides_the_semester_from_teacher(
    teacher_client: TestClient, db_session: Session
) -> None:
    # The rule follows the CURRENT state: no PUBLISHED version left in the
    # semester -> nothing of it is visible any more.
    world = _build_world(db_session)
    _set_status(db_session, world.published_version, "ARCHIVED")

    assert _ids(teacher_client.get("/api/v1/lessons/")) == []
    assert _ids(teacher_client.get("/api/v1/class-subject-requirements/")) == []
    assert (
        teacher_client.get(
            f"/api/v1/class-subject-requirements/{world.published_requirement.id}"
        ).status_code
        == 404
    )


# --- Schedule rows ---


def test_teacher_sees_only_published_schedule_rows(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)

    teacher_ids = _ids(teacher_client.get("/api/v1/schedules/"))

    assert teacher_ids == _schedule_ids(db_session, world.published_version)
    # The DRAFT of the same semester stays hidden even though its lessons
    # are visible.
    for version in (world.draft_version_same_semester, world.archived_version, world.draft_version):
        assert _ids(
            teacher_client.get("/api/v1/schedules/", params={"schedule_version_id": version.id})
        ) == []
        hidden_id = _schedule_ids(db_session, version)[0]
        assert teacher_client.get(f"/api/v1/schedules/{hidden_id}").status_code == 404
        assert client.get(f"/api/v1/schedules/{hidden_id}").status_code == 200


# --- What the frontend's 課表檢視 calls for a TEACHER ---


def test_teacher_timetable_view_requests_all_succeed(
    teacher_client: TestClient, db_session: Session
) -> None:
    # Mirrors frontend/src/pages/TimetableView.tsx + hooks/useTimetableData.ts
    # for a TEACHER opening the PUBLISHED version.
    world = _build_world(db_session)
    version_id = world.published_version.id
    semester_id = world.published_semester.id

    versions = teacher_client.get("/api/v1/schedule-versions/")
    assert [v["id"] for v in versions.json()] == [version_id]
    assert teacher_client.get(f"/api/v1/schedule-versions/{version_id}").status_code == 200
    schedules = teacher_client.get(
        "/api/v1/schedules/", params={"schedule_version_id": version_id, "limit": 1000}
    )
    lessons = teacher_client.get(
        "/api/v1/lessons/", params={"semester_id": semester_id, "limit": 1000}
    )
    requirements = teacher_client.get(
        "/api/v1/class-subject-requirements/", params={"semester_id": semester_id, "limit": 1000}
    )
    assert len(_ids(schedules)) == 2
    assert len(_ids(lessons)) == 2
    assert _ids(requirements) == [world.published_requirement.id]
    for url in (
        "/api/v1/time-slots/",
        "/api/v1/teachers/",
        "/api/v1/classes/",
        "/api/v1/subjects/",
        "/api/v1/rooms/",
        "/api/v1/semesters/",
        "/api/v1/academic-years/",
    ):
        assert teacher_client.get(url, params={"limit": 1000}).status_code == 200, url
    # Every Schedule row's lesson and that lesson's requirement are among
    # what the TEACHER could load -- the grid can resolve every row.
    lesson_by_id = {lesson["id"]: lesson for lesson in lessons.json()}
    requirement_ids = {requirement["id"] for requirement in requirements.json()}
    for schedule in schedules.json():
        lesson = lesson_by_id[schedule["lesson_id"]]
        assert lesson["class_subject_requirement_id"] in requirement_ids


def test_teacher_cannot_check_any_version(
    teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)

    for version in (world.published_version, world.draft_version, world.archived_version):
        response = teacher_client.get(f"/api/v1/schedule-versions/{version.id}/check")
        assert response.status_code == 403


def test_admin_can_still_check(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)

    response = client.get(f"/api/v1/schedule-versions/{world.published_version.id}/check")

    assert response.status_code == 200
