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
