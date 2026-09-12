from fastapi.testclient import TestClient


def _create_academic_year(client: TestClient, year: int) -> int:
    response = client.post("/api/v1/academic-years/", json={"year": year})
    academic_year_id: int = response.json()["id"]
    return academic_year_id


def _create_semester(client: TestClient, year: int) -> int:
    academic_year_id = _create_academic_year(client, year)
    response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    )
    semester_id: int = response.json()["id"]
    return semester_id


def _create_grade(client: TestClient, level: int) -> int:
    response = client.post(
        "/api/v1/grades/", json={"name": f"Grade {level}", "level": level}
    )
    grade_id: int = response.json()["id"]
    return grade_id


def _create_class(client: TestClient, level: int) -> int:
    grade_id = _create_grade(client, level)
    response = client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": f"Class {level}"}
    )
    class_id: int = response.json()["id"]
    return class_id


def _create_subject(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    subject_id: int = response.json()["id"]
    return subject_id


def _create_teacher(
    client: TestClient, name: str, min_weekly_periods: int = 0, max_weekly_periods: int = 20
) -> int:
    response = client.post(
        "/api/v1/teachers/",
        json={
            "name": name,
            "min_weekly_periods": min_weekly_periods,
            "max_weekly_periods": max_weekly_periods,
        },
    )
    teacher_id: int = response.json()["id"]
    return teacher_id


def _add_teacher_subject(client: TestClient, teacher_id: int, subject_id: int) -> None:
    response = client.post(
        f"/api/v1/teachers/{teacher_id}/subjects", json={"subject_id": subject_id}
    )
    assert response.status_code == 201


def _create_time_slot(client: TestClient, weekday: int, period: int) -> int:
    response = client.post(
        "/api/v1/time-slots/", json={"weekday": weekday, "period": period}
    )
    time_slot_id: int = response.json()["id"]
    return time_slot_id


def _create_requirement(
    client: TestClient,
    semester_id: int,
    class_id: int,
    subject_id: int,
    weekly_periods: int,
) -> int:
    response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": weekly_periods,
        },
    )
    requirement_id: int = response.json()["id"]
    return requirement_id


def _create_schedule_version(client: TestClient, semester_id: int) -> int:
    response = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": semester_id, "version_number": 1, "status": "DRAFT"},
    )
    version_id: int = response.json()["id"]
    return version_id


def _build_schedulable_semester(
    client: TestClient, year: int, weekly_periods: int = 1
) -> tuple[int, int]:
    """Builds one class/subject/requirement, a qualified teacher, and enough
    time slots to actually place `weekly_periods` lessons. Returns
    (semester_id, schedule_version_id) with generate-lessons already run.
    """
    semester_id = _create_semester(client, year)
    class_id = _create_class(client, level=year)
    subject_id = _create_subject(client, name=f"Subject {year}")
    _create_requirement(client, semester_id, class_id, subject_id, weekly_periods)

    teacher_id = _create_teacher(client, name=f"Teacher {year}")
    _add_teacher_subject(client, teacher_id, subject_id)

    for period in range(1, weekly_periods + 1):
        _create_time_slot(client, weekday=1, period=period)

    version_id = _create_schedule_version(client, semester_id)
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    assert generate_response.json()["created_count"] == weekly_periods

    return semester_id, version_id


# --- Success path ---


def test_run_scheduler_success(client: TestClient) -> None:
    _, version_id = _build_schedulable_semester(client, year=3001, weekly_periods=2)

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 200
    data = response.json()
    assert data["scheduled_count"] == 2
    assert data["backtrack_count"] == 0

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.status_code == 200
    schedules = schedules_response.json()
    assert len(schedules) == 2
    for schedule in schedules:
        assert schedule["schedule_version_id"] == version_id
        assert schedule["teacher_id"] is not None
        assert schedule["time_slot_id"] is not None


# --- Failure path: no qualified teacher -> DEFINITELY_INFEASIBLE, atomic ---


def test_run_scheduler_infeasible_returns_422_and_writes_nothing(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=3002)
    class_id = _create_class(client, level=3002)
    subject_id = _create_subject(client, name="Subject 3002")
    _create_requirement(client, semester_id, class_id, subject_id, weekly_periods=1)
    # No teacher qualified for this subject at all.
    _create_time_slot(client, weekday=1, period=1)
    version_id = _create_schedule_version(client, semester_id)
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "DEFINITELY_INFEASIBLE"
    assert len(data["lesson_failures"]) == 1
    assert data["lesson_failures"][0]["class_subject_requirement_id"]

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


# --- Task 22 regression: required_teacher_id pointing at an unqualified
# teacher must produce a non-empty, explained lesson_failures, not an
# unexplained DEFINITELY_INFEASIBLE with lesson_failures == []. ---


def test_run_scheduler_required_teacher_not_qualified_returns_explained_422(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=3005)
    class_id = _create_class(client, level=3005)
    subject_id = _create_subject(client, name="Subject 3005")
    other_subject_id = _create_subject(client, name="Other Subject 3005")

    teacher_id = _create_teacher(client, name="Teacher 3005")
    # Qualified for a DIFFERENT subject, not the one required below.
    _add_teacher_subject(client, teacher_id, other_subject_id)

    requirement_response = client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 1,
            "required_teacher_id": teacher_id,
        },
    )
    assert requirement_response.status_code == 201

    _create_time_slot(client, weekday=1, period=1)
    version_id = _create_schedule_version(client, semester_id)
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    assert generate_response.json()["created_count"] == 1

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    data = response.json()
    assert data["failure_type"] == "DEFINITELY_INFEASIBLE"
    # The whole point of this regression test: lesson_failures must NOT be
    # empty -- there is exactly one Lesson, and it has a fully explainable,
    # per-Lesson reason it can never be placed.
    assert len(data["lesson_failures"]) == 1
    reason = data["lesson_failures"][0]["reasons"][0]
    assert reason["type"] == "H6_REQUIRED_TEACHER_NOT_QUALIFIED"
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
    semester_id = _create_semester(client, year=3006)
    subject_id = _create_subject(client, name="Subject 3006")

    teacher_id = _create_teacher(
        client, name="楊老師 3006", min_weekly_periods=0, max_weekly_periods=2
    )
    _add_teacher_subject(client, teacher_id, subject_id)

    class_a = _create_class(client, level=30061)
    class_b = _create_class(client, level=30062)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_a,
            "subject_id": subject_id,
            "weekly_periods": 2,
            "required_teacher_id": teacher_id,
        },
    )
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_b,
            "subject_id": subject_id,
            "weekly_periods": 2,
            "required_teacher_id": teacher_id,
        },
    )
    for period in range(1, 5):
        _create_time_slot(client, weekday=1, period=period)

    version_id = _create_schedule_version(client, semester_id)
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
    semester_id = _create_semester(client, year=3007)
    class_id = _create_class(client, level=3007)
    subject_id = _create_subject(client, name="Subject 3007")

    teacher_id = _create_teacher(
        client, name="Teacher 3007", min_weekly_periods=0, max_weekly_periods=20
    )
    _add_teacher_subject(client, teacher_id, subject_id)

    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 3,
            "required_teacher_id": teacher_id,
        },
    )

    # Only 3 school time slots total...
    slot_ids = [_create_time_slot(client, weekday=1, period=p) for p in range(1, 4)]
    # ...but the teacher is unavailable for 2 of them, leaving only 1
    # available slot for 3 required lessons.
    for slot_id in slot_ids[1:]:
        response = client.post(
            f"/api/v1/teachers/{teacher_id}/unavailable-slots",
            json={"time_slot_id": slot_id},
        )
        assert response.status_code == 201

    version_id = _create_schedule_version(client, semester_id)
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


def test_run_scheduler_static_check_inactive_class_conflict(
    client: TestClient,
) -> None:
    _, version_id = _build_schedulable_semester(client, year=3008, weekly_periods=1)

    # Deactivate the class AFTER lessons were already generated for it --
    # generate-lessons doesn't (and shouldn't) care about is_active, so this
    # is a legitimate, reachable state, not a contrived one.
    lessons_response = client.get("/api/v1/lessons/")
    lesson = lessons_response.json()[-1]
    requirement_response = client.get(
        f"/api/v1/class-subject-requirements/{lesson['class_subject_requirement_id']}"
    )
    class_id = requirement_response.json()["class_id"]

    deactivate_response = client.patch(
        f"/api/v1/classes/{class_id}", json={"is_active": False}
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
    assert violations[0]["class_id"] == class_id

    schedules_response = client.get("/api/v1/schedules/")
    assert schedules_response.json() == []


def test_run_scheduler_static_checks_do_not_interfere_with_each_other(
    client: TestClient,
) -> None:
    """All three checks firing in the SAME run must all be reported
    together, none masking another."""
    semester_id = _create_semester(client, year=3009)
    subject_id = _create_subject(client, name="Subject 3009")

    # Overloaded teacher (workload).
    overloaded_teacher = _create_teacher(
        client, name="Overloaded 3009", max_weekly_periods=1
    )
    _add_teacher_subject(client, overloaded_teacher, subject_id)
    class_a = _create_class(client, level=30091)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_a,
            "subject_id": subject_id,
            "weekly_periods": 2,
            "required_teacher_id": overloaded_teacher,
        },
    )

    # Unavailable teacher (availability).
    unavailable_teacher = _create_teacher(
        client, name="Unavailable 3009", max_weekly_periods=20
    )
    _add_teacher_subject(client, unavailable_teacher, subject_id)
    class_b = _create_class(client, level=30092)
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_b,
            "subject_id": subject_id,
            "weekly_periods": 2,
            "required_teacher_id": unavailable_teacher,
        },
    )

    slot_ids = [_create_time_slot(client, weekday=1, period=p) for p in range(1, 3)]
    for slot_id in slot_ids:
        client.post(
            f"/api/v1/teachers/{unavailable_teacher}/unavailable-slots",
            json={"time_slot_id": slot_id},
        )

    # Inactive class (unrelated third requirement).
    class_c = _create_class(client, level=30093)
    client.patch(f"/api/v1/classes/{class_c}", json={"is_active": False})
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_c,
            "subject_id": subject_id,
            "weekly_periods": 1,
        },
    )

    version_id = _create_schedule_version(client, semester_id)
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
