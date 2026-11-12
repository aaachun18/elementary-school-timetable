from fastapi.testclient import TestClient
from tests.api_helpers import (
    create_class,
    create_enrolled_teacher,
    create_grade,
    create_record,
    create_teacher,
    create_time_slot,
    enroll_teacher,
)


def _create_academic_year(client: TestClient, year: int) -> int:
    response = client.post("/api/v1/academic-years/", json={"year": year})
    academic_year_id: int = response.json()["id"]
    return academic_year_id


def _create_record(client: TestClient, year: int) -> int:
    """v3: a semester and its 尚未排課 record -- the owner of every setting
    the test then builds."""
    academic_year_id = _create_academic_year(client, year)
    response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    )
    return create_record(client, response.json()["id"])


def _create_grade(client: TestClient, level: int) -> int:
    return create_grade(client, f"Grade {level}")


def _create_class(client: TestClient, level: int) -> int:
    grade_id = _create_grade(client, level)
    return create_class(client, grade_id, f"Class {level}")


def _create_subject(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    subject_id: int = response.json()["id"]
    return subject_id


def _create_time_slot(client: TestClient, weekday: int, period: int) -> int:
    return create_time_slot(client, weekday, period)


def _create_requirement(
    client: TestClient,
    record_id: int,
    class_id: int,
    subject_id: int,
    weekly_periods: int,
) -> int:
    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": weekly_periods,
        },
    )
    requirement_id: int = response.json()["id"]
    return requirement_id


def _build_schedulable_semester(
    client: TestClient, year: int, weekly_periods: int = 1
) -> tuple[int, int]:
    """Builds a 尚未排課 record with one class/subject/requirement, a
    teacher taking part, and enough time slots to actually place
    `weekly_periods` lessons. Returns (record_id, schedule_version_id) --
    the same record -- with generate-lessons already run.
    """
    record_id = _create_record(client, year)
    class_id = _create_class(client, level=year)
    subject_id = _create_subject(client, name=f"Subject {year}")
    _create_requirement(client, record_id, class_id, subject_id, weekly_periods)

    create_enrolled_teacher(client, record_id, f"Teacher {year}")

    for period in range(1, weekly_periods + 1):
        _create_time_slot(client, weekday=1, period=period)

    version_id = record_id
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    assert generate_response.json()["created_count"] == weekly_periods

    return record_id, version_id


# --- Success path ---


def test_run_scheduler_success(client: TestClient) -> None:
    _, version_id = _build_schedulable_semester(client, year=3001, weekly_periods=2)

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 200
    data = response.json()
    assert data["scheduled_count"] == 2
    assert data["backtrack_count"] == 0
    # v3: the record is now 自動排課.
    assert client.get(f"/api/v1/schedule-versions/{version_id}").json()["status"] == "AUTO"

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.status_code == 200
    schedules = schedules_response.json()
    assert len(schedules) == 2
    for schedule in schedules:
        assert schedule["schedule_version_id"] == version_id
        assert schedule["teacher_id"] is not None
        assert schedule["time_slot_id"] is not None


def test_run_scheduler_moves_the_record_to_newest(client: TestClient) -> None:
    """A 尚未排課 record made earlier becomes the newest once scheduled: the
    next serial (編號 1 on screen) and a fresh 建立時間."""
    _, version_id = _build_schedulable_semester(client, year=3002)
    semester_id = client.get(f"/api/v1/schedule-versions/{version_id}").json()["semester_id"]
    later_id = create_record(client, semester_id)
    before = client.get(f"/api/v1/schedule-versions/{version_id}").json()
    later = client.get(f"/api/v1/schedule-versions/{later_id}").json()
    assert before["display_number"] == 2

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 200
    after = client.get(f"/api/v1/schedule-versions/{version_id}").json()
    assert after["display_number"] == 1
    assert after["version_number"] > later["version_number"]
    assert after["created_at"] >= later["created_at"]
    assert client.get(f"/api/v1/schedule-versions/{later_id}").json()["display_number"] == 2


# --- Failure path: no qualified teacher -> DEFINITELY_INFEASIBLE, atomic ---


def test_run_scheduler_infeasible_returns_422_and_writes_nothing(
    client: TestClient,
) -> None:
    record_id = _create_record(client, year=3002)
    class_id = _create_class(client, level=3002)
    subject_id = _create_subject(client, name="Subject 3002")
    _create_requirement(client, record_id, class_id, subject_id, weekly_periods=1)
    # No teacher qualified for this subject at all.
    _create_time_slot(client, weekday=1, period=1)
    version_id = record_id
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    # Task 38: a zero-candidate-teacher Lesson is now caught by
    # check_static_feasibility() itself (a 4th static check), before
    # schedule_backtracking() is ever called -- so this reports
    # STATIC_CHECK_FAILED, not DEFINITELY_INFEASIBLE (that label is now
    # reserved for cases the SEARCH itself exhausts). Same underlying
    # explanation either way, just caught earlier.
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    assert data["backtrack_count"] == 0
    assert len(data["lesson_failures"]) == 1
    assert data["lesson_failures"][0]["class_subject_requirement_id"]

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []
    # v3: a failed run leaves the record 尚未排課 -- never a partial result.
    assert client.get(f"/api/v1/schedule-versions/{version_id}").json()["status"] == (
        "NOT_SCHEDULED"
    )


# --- Task 22 regression: required_teacher_id pointing at an unqualified
# teacher must produce a non-empty, explained lesson_failures, not an
# unexplained DEFINITELY_INFEASIBLE with lesson_failures == []. ---


def test_run_scheduler_required_teacher_not_participating_returns_explained_422(
    client: TestClient,
) -> None:
    record_id = _create_record(client, year=3005)
    class_id = _create_class(client, level=3005)
    subject_id = _create_subject(client, name="Subject 3005")

    # Task 98 (was: qualified for a different subject): another teacher
    # takes part in the semester, the required one doesn't.
    teacher_id = create_teacher(client, "Teacher 3005")
    create_enrolled_teacher(client, record_id, "Other Teacher 3005")

    requirement_response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 1,
            "required_teacher_id": teacher_id,
        },
    )
    assert requirement_response.status_code == 201

    _create_time_slot(client, weekday=1, period=1)
    version_id = record_id
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    assert generate_response.json()["created_count"] == 1

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    # Task 38: same reclassification as
    # test_run_scheduler_infeasible_returns_422_and_writes_nothing above --
    # check_static_feasibility()'s 4th check now catches this before any
    # search, so it's STATIC_CHECK_FAILED, not DEFINITELY_INFEASIBLE.
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    assert data["backtrack_count"] == 0
    # The whole point of this regression test: lesson_failures must NOT be
    # empty -- there is exactly one Lesson, and it has a fully explainable,
    # per-Lesson reason it can never be placed.
    assert len(data["lesson_failures"]) == 1
    reason = data["lesson_failures"][0]["reasons"][0]
    assert reason["type"] == "H6_REQUIRED_TEACHER_NOT_PARTICIPATING"
    assert reason["teacher_id"] == teacher_id

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


# --- Task 23: pre-search static feasibility checks ---
# For all three: schedule_backtracking() is called strictly AFTER the
# static-check early return in services/scheduler.py::run_scheduler() (see
# that function's source), so backtrack_count == 0 here is a structural
# guarantee that no search ran at all, not a coincidence -- and the
# STATIC_* violation `type` values are produced ONLY by
# scheduling_engine/static_feasibility.py, never by the search algorithms
# themselves, which is further, independent confirmation of where the
# failure was actually caught.


def test_run_scheduler_static_check_teacher_workload_exceeded(
    client: TestClient,
) -> None:
    """Reproduces the 楊老師 scenario from the Task 21/22 investigation:
    one teacher pinned via required_teacher_id across multiple
    requirements, whose combined Lesson count exceeds max_weekly_periods."""
    record_id = _create_record(client, year=3006)
    subject_id = _create_subject(client, name="Subject 3006")

    teacher_id = create_enrolled_teacher(
        client, record_id, "楊老師 3006", min_weekly_periods=0, max_weekly_periods=2
    )

    class_a = _create_class(client, level=30061)
    class_b = _create_class(client, level=30062)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_a,
            "subject_id": subject_id,
            "weekly_periods": 2,
            "required_teacher_id": teacher_id,
        },
    )
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_b,
            "subject_id": subject_id,
            "weekly_periods": 2,
            "required_teacher_id": teacher_id,
        },
    )
    for period in range(1, 5):
        _create_time_slot(client, weekday=1, period=period)

    version_id = record_id
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    assert generate_response.json()["created_count"] == 4  # 2 + 2, exceeds cap of 2

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    assert data["backtrack_count"] == 0
    assert data["lesson_failures"] == []
    violations = data["post_hoc_violations"]
    assert len(violations) == 1
    assert violations[0]["type"] == "STATIC_TEACHER_WORKLOAD_EXCEEDED"
    assert violations[0]["teacher_id"] == teacher_id

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


def test_run_scheduler_static_check_teacher_availability_insufficient(
    client: TestClient,
) -> None:
    record_id = _create_record(client, year=3007)
    class_id = _create_class(client, level=3007)
    subject_id = _create_subject(client, name="Subject 3007")

    teacher_id = create_enrolled_teacher(
        client, record_id, "Teacher 3007", min_weekly_periods=0, max_weekly_periods=20
    )

    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 3,
            "required_teacher_id": teacher_id,
        },
    )

    # Only 3 school time slots total...
    slot_ids = [_create_time_slot(client, weekday=1, period=p) for p in range(1, 4)]
    # ...but the teacher is unavailable for 2 of them this semester,
    # leaving only 1 available slot for 3 required lessons.
    enroll_teacher(client, record_id, teacher_id, unavailable_time_slot_ids=slot_ids[1:])

    version_id = record_id
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    assert generate_response.json()["created_count"] == 3

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    assert data["backtrack_count"] == 0
    violations = data["post_hoc_violations"]
    assert len(violations) == 1
    assert violations[0]["type"] == "STATIC_TEACHER_AVAILABILITY_INSUFFICIENT"
    assert violations[0]["teacher_id"] == teacher_id

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


def test_run_scheduler_static_check_inactive_subject_conflict(
    client: TestClient,
) -> None:
    """Classes have no is_active any more (always active); H12's pre-check
    is exercised through a deactivated subject instead."""
    _, version_id = _build_schedulable_semester(client, year=3008, weekly_periods=1)

    # Deactivate the subject AFTER lessons were already generated for it --
    # generate-lessons doesn't (and shouldn't) care about is_active, so this
    # is a legitimate, reachable state, not a contrived one.
    lessons_response = client.get("/api/v1/lessons/")
    lesson = lessons_response.json()[-1]
    requirement_response = client.get(
        f"/api/v1/class-subject-requirements/{lesson['class_subject_requirement_id']}"
    )
    subject_id = requirement_response.json()["subject_id"]

    deactivate_response = client.patch(
        f"/api/v1/subjects/{subject_id}", json={"is_active": False}
    )
    assert deactivate_response.status_code == 200

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    assert data["backtrack_count"] == 0
    violations = data["post_hoc_violations"]
    assert len(violations) == 1
    assert violations[0]["type"] == "STATIC_INACTIVE_ENTITY_CONFLICT"
    assert violations[0]["subject_id"] == subject_id

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


def test_run_scheduler_static_checks_do_not_interfere_with_each_other(
    client: TestClient,
) -> None:
    """All three checks firing in the SAME run must all be reported
    together, none masking another."""
    record_id = _create_record(client, year=3009)
    subject_id = _create_subject(client, name="Subject 3009")

    # Overloaded teacher (workload).
    overloaded_teacher = create_enrolled_teacher(
        client, record_id, "Overloaded 3009", max_weekly_periods=1
    )
    class_a = _create_class(client, level=30091)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_a,
            "subject_id": subject_id,
            "weekly_periods": 2,
            "required_teacher_id": overloaded_teacher,
        },
    )

    # Unavailable teacher (availability).
    unavailable_teacher = create_enrolled_teacher(
        client, record_id, "Unavailable 3009", max_weekly_periods=20
    )
    class_b = _create_class(client, level=30092)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_b,
            "subject_id": subject_id,
            "weekly_periods": 2,
            "required_teacher_id": unavailable_teacher,
        },
    )

    slot_ids = [_create_time_slot(client, weekday=1, period=p) for p in range(1, 3)]
    enroll_teacher(
        client, record_id, unavailable_teacher, unavailable_time_slot_ids=slot_ids
    )

    # Inactive subject (unrelated third requirement).
    class_c = _create_class(client, level=30093)
    inactive_subject = _create_subject(client, name="Inactive Subject 3009")
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_c,
            "subject_id": inactive_subject,
            "weekly_periods": 1,
        },
    )
    client.patch(f"/api/v1/subjects/{inactive_subject}", json={"is_active": False})

    version_id = record_id
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    assert data["backtrack_count"] == 0
    types = {v["type"] for v in data["post_hoc_violations"]}
    assert types == {
        "STATIC_TEACHER_WORKLOAD_EXCEEDED",
        "STATIC_TEACHER_AVAILABILITY_INSUFFICIENT",
        "STATIC_INACTIVE_ENTITY_CONFLICT",
    }


def test_run_scheduler_static_check_and_zero_candidate_teacher_together(
    client: TestClient,
) -> None:
    """Task 38 regression: reproduces the exact bug a real user hit --
    STATIC_TEACHER_WORKLOAD_EXCEEDED (a whole-batch static check) and a
    zero-candidate-teacher problem (a per-Lesson problem, for a completely
    unrelated requirement -- Task 98: its required teacher doesn't take
    part in the semester) firing in the SAME run.
    Before the fix, run_scheduler() returned as soon as
    check_static_feasibility() found the workload problem, WITHOUT ever
    calling schedule_backtracking() -- the only place that used to catch
    zero-candidate-teacher Lessons -- so the response only ever reported the
    workload violation and lesson_failures came back empty, silently
    dropping the second failure reason entirely.
    """
    record_id = _create_record(client, year=3010)

    # Requirement 1: overloaded teacher (workload) -- same shape as
    # test_run_scheduler_static_check_teacher_workload_exceeded.
    workload_subject_id = _create_subject(client, name="Workload Subject 3010")
    overloaded_teacher = create_enrolled_teacher(
        client, record_id, "Overloaded 3010", max_weekly_periods=1
    )
    class_a = _create_class(client, level=30101)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_a,
            "subject_id": workload_subject_id,
            "weekly_periods": 2,
            "required_teacher_id": overloaded_teacher,
        },
    )

    # Requirement 2: a completely unrelated subject whose required teacher
    # doesn't take part in the semester.
    unteachable_subject_id = _create_subject(client, name="Unteachable Subject 3010")
    absent_teacher = create_teacher(client, "Absent 3010")
    class_b = _create_class(client, level=30102)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "schedule_version_id": record_id,
            "class_id": class_b,
            "subject_id": unteachable_subject_id,
            "weekly_periods": 1,
            "required_teacher_id": absent_teacher,
        },
    )

    # Enough time slots that the overloaded teacher's problem is PURELY a
    # workload one -- 2 slots for their 2 required lessons, so
    # STATIC_TEACHER_AVAILABILITY_INSUFFICIENT does not also fire and
    # muddy what this test is isolating.
    for period in range(1, 3):
        _create_time_slot(client, weekday=1, period=period)

    version_id = record_id
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    assert generate_response.json()["created_count"] == 3  # 2 + 1

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    assert data["backtrack_count"] == 0

    # The workload problem: still reported, exactly as before.
    post_hoc_types = {v["type"] for v in data["post_hoc_violations"]}
    assert post_hoc_types == {"STATIC_TEACHER_WORKLOAD_EXCEEDED"}

    # The zero-candidate-teacher problem: MUST also be reported now, not
    # silently dropped.
    assert len(data["lesson_failures"]) == 1
    lesson_failure = data["lesson_failures"][0]
    assert lesson_failure["reasons"][0]["type"] == "H6_REQUIRED_TEACHER_NOT_PARTICIPATING"
    assert lesson_failure["reasons"][0]["subject_id"] == unteachable_subject_id

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


# --- 404 ---


def test_run_scheduler_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/schedule-versions/999999/run-scheduler")

    assert response.status_code == 404


# --- 403 for non-ADMIN ---


def test_run_scheduler_forbidden_for_teacher(
    client: TestClient, teacher_client: TestClient
) -> None:
    _, version_id = _build_schedulable_semester(client, year=3003, weekly_periods=1)

    response = teacher_client.post(
        f"/api/v1/schedule-versions/{version_id}/run-scheduler"
    )

    assert response.status_code == 403

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


# --- Already-scheduled guard ---


def test_run_scheduler_already_scheduled_returns_409(client: TestClient) -> None:
    """v3: only a 尚未排課 record is scheduled; an 自動排課 one is never
    overwritten."""
    _, version_id = _build_schedulable_semester(client, year=3004, weekly_periods=1)

    first = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")
    assert first.status_code == 200

    second = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert second.status_code == 409

    schedules_response = client.get("/api/v1/schedules/")
    assert len(schedules_response.json()) == 1


# --- Task 28: Lesson.fixed_time_slot_id end-to-end ---


def test_run_scheduler_respects_fixed_time_slot(client: TestClient) -> None:
    """End-to-end: fix one of two weekly lessons to a specific time slot via
    the API, then confirm run-scheduler actually honors it -- not just at
    the engine-unit level (already covered in
    tests/scheduling_engine/test_fixed_time_slot.py), but through the real
    DB round trip (Lesson.fixed_time_slot_id -> LessonAssignment.time_slot_id
    -> Schedule.time_slot_id)."""
    _, version_id = _build_schedulable_semester(client, year=3010, weekly_periods=2)

    lessons_response = client.get("/api/v1/lessons/")
    lessons = lessons_response.json()
    assert len(lessons) == 2
    lesson_to_fix = lessons[0]

    # The two time slots created by _build_schedulable_semester are weekday
    # 1, periods 1 and 2 -- fetch the second one and fix the lesson to it,
    # deliberately NOT the one that would be tried first.
    time_slots_response = client.get("/api/v1/time-slots/")
    time_slot_id = next(
        t["id"] for t in time_slots_response.json() if t["period"] == 2
    )
    fix_response = client.patch(
        f"/api/v1/lessons/{lesson_to_fix['id']}/fix-time-slot",
        json={"time_slot_id": time_slot_id},
    )
    assert fix_response.status_code == 200

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 200
    assert response.json()["scheduled_count"] == 2

    schedules_response = client.get("/api/v1/schedules/")
    schedules = schedules_response.json()
    fixed_schedule = next(
        s for s in schedules if s["lesson_id"] == lesson_to_fix["id"]
    )
    assert fixed_schedule["time_slot_id"] == time_slot_id


# --- Task 81: impossible fixed time slots are reported before the search ---


def _fix(client: TestClient, lesson_id: int, time_slot_id: int) -> None:
    response = client.patch(
        f"/api/v1/lessons/{lesson_id}/fix-time-slot", json={"time_slot_id": time_slot_id}
    )
    assert response.status_code == 200, response.json()


def test_run_scheduler_fixed_to_non_teaching_slot_returns_static_422(
    client: TestClient,
) -> None:
    _, version_id = _build_schedulable_semester(client, year=3020, weekly_periods=2)
    lunch = create_time_slot(client, 1, 5, is_teaching_period=False, label="午休")
    lessons = client.get("/api/v1/lessons/", params={"schedule_version_id": version_id}).json()
    fixed_lesson = lessons[0]
    _fix(client, fixed_lesson["id"], lunch)

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    # Same shape as every other static failure: STATIC_CHECK_FAILED, the
    # reasons in post_hoc_violations, nothing written.
    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    assert data["backtrack_count"] == 0
    assert data["lesson_failures"] == []
    assert len(data["post_hoc_violations"]) == 1
    violation = data["post_hoc_violations"][0]
    assert violation["type"] == "STATIC_FIXED_SLOT_NON_TEACHING"
    assert violation["lesson_id"] == fixed_lesson["id"]
    assert violation["class_subject_requirement_id"] == fixed_lesson["class_subject_requirement_id"]
    assert violation["time_slot_id"] == lunch
    assert violation["class_id"] is not None and violation["subject_id"] is not None
    assert client.get("/api/v1/schedules/").json() == []


def test_run_scheduler_two_fixed_lessons_of_one_class_in_one_slot_returns_static_422(
    client: TestClient,
) -> None:
    _, version_id = _build_schedulable_semester(client, year=3021, weekly_periods=2)
    slot = next(t["id"] for t in client.get("/api/v1/time-slots/").json() if t["period"] == 1)
    lessons = client.get("/api/v1/lessons/", params={"schedule_version_id": version_id}).json()
    for lesson in lessons:
        _fix(client, lesson["id"], slot)

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    types = sorted(v["type"] for v in data["post_hoc_violations"])
    assert "STATIC_FIXED_SLOT_CLASS_CLASH" in types
    clash_lessons = {
        v["lesson_id"]
        for v in data["post_hoc_violations"]
        if v["type"] == "STATIC_FIXED_SLOT_CLASS_CLASH"
    }
    assert clash_lessons == {lesson["id"] for lesson in lessons}
    assert client.get("/api/v1/schedules/").json() == []


# --- Task 32.8 regression: generate-lessons called twice must never make
# the numbers a caller displays together look contradictory. ---


def test_generate_lessons_called_twice_then_run_scheduler_reports_consistent_counts(
    client: TestClient,
) -> None:
    """Reproduces the exact scenario behind the reported "共 0 堂課待排" /
    "成功排定 26 堂課" contradiction: generate-lessons gets called on a
    version whose lessons were already synced by an earlier call (in the
    real bug report, an earlier task/test run; here, simply calling it
    twice in a row). The second call's created_count correctly drops to 0
    -- that's the diff-sync design, not a bug -- but total_lesson_count
    must still report the real total, and that real total must match what
    run-scheduler actually schedules right after.
    """
    _, version_id = _build_schedulable_semester(client, year=3011, weekly_periods=3)

    # Second call: nothing new to create, but the lessons still exist.
    second_generate = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    assert second_generate.status_code == 200
    assert second_generate.json()["created_count"] == 0
    assert second_generate.json()["total_lesson_count"] == 3

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 200
    # The number the console shows as "共 X 堂課待排" (total_lesson_count)
    # and the number it shows as "成功排定 X 堂課" (scheduled_count) must
    # now agree -- both 3, never 0-vs-3.
    assert response.json()["scheduled_count"] == second_generate.json()[
        "total_lesson_count"
    ]


def test_run_scheduler_keeps_homeroom_teachers_in_their_own_class(
    client: TestClient,
) -> None:
    """導師 rule: two classes, each with three 1-period subjects and no
    required teacher, and only their two 導師 taking part. A timetable
    keeping every 導師 in their own class exists, so the scheduler must
    find it (by chance it would happen once in 64 runs)."""
    record_id = _create_record(client, 3012)
    grade_id = _create_grade(client, 3012)
    class_a = create_class(client, grade_id, "Class A")
    class_b = create_class(client, grade_id, "Class B")
    for index in range(3):
        _create_requirement(client, record_id, class_a, _create_subject(client, f"A{index}"), 1)
        _create_requirement(client, record_id, class_b, _create_subject(client, f"B{index}"), 1)
    for period in range(1, 4):
        _create_time_slot(client, weekday=1, period=period)
    teacher_a = create_teacher(client, "導師 A")
    teacher_b = create_teacher(client, "導師 B")
    response = client.put(
        f"/api/v1/schedule-versions/{record_id}/teachers",
        json={
            "teachers": [
                {
                    "teacher_id": teacher_id,
                    "min_weekly_periods": 0,
                    "max_weekly_periods": 20,
                    "unavailable_time_slot_ids": [],
                    "homeroom_class_id": class_id,
                }
                for teacher_id, class_id in ((teacher_a, class_a), (teacher_b, class_b))
            ]
        },
    )
    assert response.status_code == 200, response.json()
    client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    response = client.post(f"/api/v1/schedule-versions/{record_id}/run-scheduler")

    assert response.status_code == 200, response.json()
    lessons = {lesson["id"]: lesson for lesson in client.get("/api/v1/lessons/").json()}
    requirements = {
        requirement["id"]: requirement
        for requirement in client.get(
            f"/api/v1/class-subject-requirements/?schedule_version_id={record_id}"
        ).json()
    }
    schedules = [
        schedule
        for schedule in client.get("/api/v1/schedules/").json()
        if schedule["schedule_version_id"] == record_id
    ]
    assert len(schedules) == 6
    homeroom_of = {class_a: teacher_a, class_b: teacher_b}
    for schedule in schedules:
        requirement = requirements[lessons[schedule["lesson_id"]]["class_subject_requirement_id"]]
        assert schedule["teacher_id"] == homeroom_of[requirement["class_id"]]
