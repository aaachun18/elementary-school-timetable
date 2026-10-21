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
from tests.conftest import get_test_school_id, mark_status_in_db
from tests.test_reassign_teacher import Builder

# Task 72 / v3: what a TEACHER may read -- only the published record and
# everything it owns: its lessons, class-subject requirements, Schedule
# rows and settings (list = silent filter, single record = the usual 404);
# the check endpoint is 教學組長-only. The 教學組長 is unaffected. Test data
# is written straight to the database.


@dataclass
class ScopeWorld:
    """Four records, one course each:
    - published: 自動排課, published;
    - unpublished_same_semester: 手動排課 of the same semester;
    - other_semester: 自動排課 of semester 2, not published;
    - not_scheduled (another academic year): 尚未排課."""

    published_semester: Semester
    published: ScheduleVersion
    unpublished_same_semester: ScheduleVersion
    other_semester: ScheduleVersion
    not_scheduled: ScheduleVersion
    published_requirement: ClassSubjectRequirement
    unpublished_requirement: ClassSubjectRequirement
    other_semester_requirement: ClassSubjectRequirement
    not_scheduled_requirement: ClassSubjectRequirement

    def hidden(self) -> list[tuple[ScheduleVersion, ClassSubjectRequirement]]:
        return [
            (self.unpublished_same_semester, self.unpublished_requirement),
            (self.other_semester, self.other_semester_requirement),
            (self.not_scheduled, self.not_scheduled_requirement),
        ]


def _build_world(db: Session) -> ScopeWorld:
    builder = Builder(db)
    semester_2 = builder.semester_in_year(number=2)
    other_year = AcademicYear(school_id=get_test_school_id(db), year=6002, is_active=True)
    db.add(other_year)
    db.flush()
    other_year_semester = Semester(academic_year_id=other_year.id, number=1, is_active=True)
    db.add(other_year_semester)
    db.commit()

    english = builder.subject("英文")
    teacher = builder.teacher("老師")
    class_ = builder.class_("一班")

    published = builder.version(status="AUTO")
    published_requirement = builder.course(published, class_, english, teacher, [0, 1])
    mark_status_in_db(db, published.id, "AUTO", is_published=True)
    unpublished_same_semester = builder.version(status="MANUAL")
    unpublished_requirement = builder.course(
        unpublished_same_semester, class_, english, teacher, [0, 1]
    )
    other_semester = builder.version(semester=semester_2, status="AUTO")
    other_semester_requirement = builder.course(other_semester, class_, english, teacher, [2])
    not_scheduled = builder.version(semester=other_year_semester, status="NOT_SCHEDULED")
    not_scheduled_requirement = builder.course(not_scheduled, class_, english, teacher, [3])

    return ScopeWorld(
        published_semester=builder.semester,
        published=published,
        unpublished_same_semester=unpublished_same_semester,
        other_semester=other_semester,
        not_scheduled=not_scheduled,
        published_requirement=published_requirement,
        unpublished_requirement=unpublished_requirement,
        other_semester_requirement=other_semester_requirement,
        not_scheduled_requirement=not_scheduled_requirement,
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


def test_teacher_lists_only_lessons_of_the_published_record(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)

    teacher_ids = _ids(teacher_client.get("/api/v1/lessons/"))
    admin_ids = _ids(client.get("/api/v1/lessons/"))

    assert teacher_ids == _lesson_ids(db_session, world.published_requirement)
    assert admin_ids == sorted(
        _lesson_ids(db_session, world.published_requirement)
        + [
            lesson_id
            for _, requirement in world.hidden()
            for lesson_id in _lesson_ids(db_session, requirement)
        ]
    )


def test_teacher_lesson_record_filter_respects_visibility(
    teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)

    def listed(version: ScheduleVersion) -> list[int]:
        return _ids(
            teacher_client.get("/api/v1/lessons/", params={"schedule_version_id": version.id})
        )

    assert listed(world.published) == _lesson_ids(db_session, world.published_requirement)
    for version, _ in world.hidden():
        assert listed(version) == []


def test_teacher_lesson_pages_join_up(teacher_client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)

    first = _ids(teacher_client.get("/api/v1/lessons/", params={"skip": 0, "limit": 1}))
    second = _ids(teacher_client.get("/api/v1/lessons/", params={"skip": 1, "limit": 1}))
    rest = _ids(teacher_client.get("/api/v1/lessons/", params={"skip": 2, "limit": 1}))

    assert first + second + rest == _lesson_ids(db_session, world.published_requirement)
    assert rest == []


def test_teacher_get_lesson_of_a_hidden_record_is_404(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    visible_id = _lesson_ids(db_session, world.published_requirement)[0]

    assert teacher_client.get(f"/api/v1/lessons/{visible_id}").status_code == 200
    for _, requirement in world.hidden():
        lesson_id = _lesson_ids(db_session, requirement)[0]
        response = teacher_client.get(f"/api/v1/lessons/{lesson_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Lesson not found"
        # The 教學組長 is unaffected.
        assert client.get(f"/api/v1/lessons/{lesson_id}").status_code == 200


# --- Class-subject requirements ---


def test_teacher_lists_only_requirements_of_the_published_record(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    url = "/api/v1/class-subject-requirements/"

    assert _ids(teacher_client.get(url)) == [world.published_requirement.id]
    assert _ids(client.get(url)) == sorted(
        [world.published_requirement.id] + [requirement.id for _, requirement in world.hidden()]
    )
    assert _ids(
        teacher_client.get(url, params={"schedule_version_id": world.other_semester.id})
    ) == []
    assert _ids(
        teacher_client.get(url, params={"schedule_version_id": world.published.id})
    ) == [world.published_requirement.id]


def test_teacher_get_requirement_of_a_hidden_record_is_404(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    url = "/api/v1/class-subject-requirements"

    assert teacher_client.get(f"{url}/{world.published_requirement.id}").status_code == 200
    for _, requirement in world.hidden():
        response = teacher_client.get(f"{url}/{requirement.id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "ClassSubjectRequirement not found"
        assert client.get(f"{url}/{requirement.id}").status_code == 200


def test_publishing_another_record_hides_the_old_one_from_teacher(
    client: TestClient, teacher_client: TestClient, db_session: Session
) -> None:
    # The rule follows the CURRENT state: once another record of the
    # semester is published, nothing of the old one is visible any more.
    world = _build_world(db_session)
    assert client.post(
        f"/api/v1/schedule-versions/{world.unpublished_same_semester.id}/publish"
    ).status_code == 200

    assert _ids(teacher_client.get("/api/v1/class-subject-requirements/")) == [
        world.unpublished_requirement.id
    ]
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

    assert teacher_ids == _schedule_ids(db_session, world.published)
    for version, _ in world.hidden():
        assert _ids(
            teacher_client.get("/api/v1/schedules/", params={"schedule_version_id": version.id})
        ) == []
        hidden_id = _schedule_ids(db_session, version)[0]
        assert teacher_client.get(f"/api/v1/schedules/{hidden_id}").status_code == 404
        assert client.get(f"/api/v1/schedules/{hidden_id}").status_code == 200


# --- What the frontend's 檢視課表 calls for a TEACHER ---


def test_teacher_timetable_view_requests_all_succeed(
    teacher_client: TestClient, db_session: Session
) -> None:
    # Mirrors frontend/src/hooks/useTimetableData.ts for a TEACHER opening
    # the published record.
    world = _build_world(db_session)
    version_id = world.published.id

    versions = teacher_client.get("/api/v1/schedule-versions/")
    assert [v["id"] for v in versions.json()] == [version_id]
    assert teacher_client.get(f"/api/v1/schedule-versions/{version_id}").status_code == 200
    schedules = teacher_client.get(
        "/api/v1/schedules/", params={"schedule_version_id": version_id, "limit": 1000}
    )
    lessons = teacher_client.get(
        "/api/v1/lessons/", params={"schedule_version_id": version_id, "limit": 1000}
    )
    requirements = teacher_client.get(
        "/api/v1/class-subject-requirements/",
        params={"schedule_version_id": version_id, "limit": 1000},
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

    for version in (world.published, world.other_semester, world.not_scheduled):
        response = teacher_client.get(f"/api/v1/schedule-versions/{version.id}/check")
        assert response.status_code == 403


def test_admin_can_still_check(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)

    response = client.get(f"/api/v1/schedule-versions/{world.published.id}/check")

    assert response.status_code == 200
