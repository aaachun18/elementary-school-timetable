from fastapi.testclient import TestClient
from tests.api_helpers import (
    create_class,
    create_grade,
    create_record,
    create_time_slot,
    db_of,
    mark_status,
)

from app.models.lesson import Lesson
from app.models.schedule import Schedule


def _create_academic_year(client: TestClient, year: int) -> int:
    response = client.post("/api/v1/academic-years/", json={"year": year})
    academic_year_id: int = response.json()["id"]
    return academic_year_id


def _create_semester(client: TestClient, year: int, number: int = 1) -> int:
    academic_year_id = _create_academic_year(client, year)
    response = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": number},
    )
    semester_id: int = response.json()["id"]
    return semester_id


def _create_grade(client: TestClient, level: int) -> int:
    return create_grade(client, f"Grade {level}")


def _create_class(client: TestClient, level: int) -> int:
    grade_id = _create_grade(client, level)
    return create_class(client, grade_id, f"Class {level}")


def _create_subject(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    subject_id: int = response.json()["id"]
    return subject_id


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
    assert response.status_code == 201, response.json()
    requirement_id: int = response.json()["id"]
    return requirement_id


def _create_record(client: TestClient, year: int) -> int:
    return create_record(client, _create_semester(client, year))


# --- Standard CRUD ---


def test_create_schedule_version_is_not_scheduled_with_the_next_number(
    client: TestClient,
) -> None:
    semester_id = _create_semester(client, year=2061)

    response = client.post("/api/v1/schedule-versions/", json={"semester_id": semester_id})

    assert response.status_code == 201
    data = response.json()
    assert data["semester_id"] == semester_id
    assert data["version_number"] == 1
    assert data["status"] == "NOT_SCHEDULED"
    assert data["is_published"] is False
    assert data["copied_from_number"] is None
    assert data["editing_source_id"] is None
    assert data["note"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_numbers_are_one_sequence_for_the_whole_school(client: TestClient) -> None:
    """v3: 排課紀錄's 編號 runs across semesters, never restarting."""
    first_semester = _create_semester(client, year=2062)
    second_semester = _create_semester(client, year=2063)

    numbers = [
        client.post("/api/v1/schedule-versions/", json={"semester_id": semester_id}).json()[
            "version_number"
        ]
        for semester_id in (first_semester, second_semester, first_semester)
    ]

    assert numbers == [1, 2, 3]


def test_a_deleted_number_is_not_reused_while_a_higher_one_exists(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2071)
    first = create_record(client, semester_id)
    create_record(client, semester_id)
    assert client.delete(f"/api/v1/schedule-versions/{first}").status_code == 204

    response = client.post("/api/v1/schedule-versions/", json={"semester_id": semester_id})

    assert response.json()["version_number"] == 3


def test_create_schedule_version_of_unknown_semester_is_422(client: TestClient) -> None:
    response = client.post("/api/v1/schedule-versions/", json={"semester_id": 999999})

    assert response.status_code == 422


def test_list_is_newest_first(client: TestClient) -> None:
    semester_id = _create_semester(client, year=2064)
    ids = [create_record(client, semester_id) for _ in range(3)]

    response = client.get("/api/v1/schedule-versions/")

    assert response.status_code == 200
    assert [version["id"] for version in response.json()] == list(reversed(ids))


def test_list_leaves_out_working_copies(client: TestClient) -> None:
    record_id = _create_record(client, year=2065)
    mark_status(client, record_id, "EDITING")

    listed = [version["id"] for version in client.get("/api/v1/schedule-versions/").json()]

    assert record_id not in listed
    # Still readable on its own -- the edit page works on it.
    assert client.get(f"/api/v1/schedule-versions/{record_id}").status_code == 200


def test_get_schedule_version_by_id(client: TestClient) -> None:
    record_id = _create_record(client, year=2066)

    response = client.get(f"/api/v1/schedule-versions/{record_id}")

    assert response.status_code == 200
    assert response.json()["id"] == record_id


def test_get_schedule_version_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/schedule-versions/999999")

    assert response.status_code == 404


def test_patch_sets_and_clears_the_note(client: TestClient) -> None:
    record_id = _create_record(client, year=2067)

    response = client.patch(
        f"/api/v1/schedule-versions/{record_id}", json={"note": "  王老師上三年級自然課版  "}
    )
    assert response.status_code == 200
    assert response.json()["note"] == "王老師上三年級自然課版"

    cleared = client.patch(f"/api/v1/schedule-versions/{record_id}", json={"note": "  "})
    assert cleared.json()["note"] is None


def test_patch_note_works_on_a_published_record(client: TestClient) -> None:
    """The 備註 describes the record, it isn't part of the timetable."""
    record_id = _create_record(client, year=2068)
    mark_status(client, record_id, "AUTO", is_published=True)

    response = client.patch(f"/api/v1/schedule-versions/{record_id}", json={"note": "正式版"})

    assert response.status_code == 200
    assert response.json()["note"] == "正式版"


def test_patch_cannot_change_status_or_number(client: TestClient) -> None:
    record_id = _create_record(client, year=2069)

    response = client.patch(
        f"/api/v1/schedule-versions/{record_id}",
        json={"status": "AUTO", "version_number": 9, "is_published": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "NOT_SCHEDULED"
    assert data["version_number"] == 1
    assert data["is_published"] is False


def test_patch_note_too_long_is_422(client: TestClient) -> None:
    record_id = _create_record(client, year=2070)

    response = client.patch(f"/api/v1/schedule-versions/{record_id}", json={"note": "字" * 201})

    assert response.status_code == 422


def test_update_schedule_version_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/schedule-versions/999999", json={"note": "x"})

    assert response.status_code == 404


def test_delete_schedule_version(client: TestClient) -> None:
    record_id = _create_record(client, year=2072)

    response = client.delete(f"/api/v1/schedule-versions/{record_id}")

    assert response.status_code == 204
    assert client.get(f"/api/v1/schedule-versions/{record_id}").status_code == 404


def test_delete_schedule_version_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/schedule-versions/999999")

    assert response.status_code == 404


# --- generate-lessons (diff sync) ---


def test_generate_lessons_creates_missing_lessons(client: TestClient) -> None:
    record_id = _create_record(client, year=2073)
    class_id = _create_class(client, level=10)
    subject_id = _create_subject(client, name="Math 2073")
    _create_requirement(client, record_id, class_id, subject_id, weekly_periods=3)

    response = client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 3
    assert len(data["created_lessons"]) == 3
    sequence_numbers = sorted(
        lesson["sequence_number"] for lesson in data["created_lessons"]
    )
    assert sequence_numbers == [1, 2, 3]

    lessons_response = client.get("/api/v1/lessons/")
    assert lessons_response.status_code == 200
    assert len(lessons_response.json()) == 3


def test_generate_lessons_only_for_its_own_record(client: TestClient) -> None:
    """v3: two records of one semester each have their own requirements
    and lessons."""
    semester_id = _create_semester(client, year=2074)
    first = create_record(client, semester_id)
    second = create_record(client, semester_id)
    class_id = _create_class(client, level=11)
    subject_id = _create_subject(client, name="Math 2074")
    _create_requirement(client, first, class_id, subject_id, weekly_periods=2)
    _create_requirement(client, second, class_id, subject_id, weekly_periods=3)

    first_result = client.post(f"/api/v1/schedule-versions/{first}/generate-lessons").json()
    second_result = client.post(f"/api/v1/schedule-versions/{second}/generate-lessons").json()

    assert (first_result["created_count"], first_result["total_lesson_count"]) == (2, 2)
    assert (second_result["created_count"], second_result["total_lesson_count"]) == (3, 3)
    first_lessons = client.get(
        "/api/v1/lessons/", params={"schedule_version_id": first}
    ).json()
    assert len(first_lessons) == 2


def test_generate_lessons_is_idempotent_when_already_synced(
    client: TestClient,
) -> None:
    record_id = _create_record(client, year=2075)
    class_id = _create_class(client, level=12)
    subject_id = _create_subject(client, name="Math 2075")
    _create_requirement(client, record_id, class_id, subject_id, weekly_periods=2)

    first = client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")
    assert first.json()["created_count"] == 2
    assert first.json()["total_lesson_count"] == 2

    second = client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    assert second.status_code == 200
    # Task 32.8 regression: created_count correctly drops to 0 (nothing NEW
    # to insert, diff-sync is idempotent) but total_lesson_count must NOT
    # also drop to 0 -- the 2 lessons created by the first call still
    # exist.
    assert second.json()["created_count"] == 0
    assert second.json()["total_lesson_count"] == 2


def test_generate_lessons_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/schedule-versions/999999/generate-lessons")

    assert response.status_code == 404


def test_generate_lessons_over_provisioned_returns_409_and_creates_nothing(
    client: TestClient,
) -> None:
    record_id = _create_record(client, year=2076)
    class_id = _create_class(client, level=13)
    subject_id = _create_subject(client, name="Math 2076")
    requirement_id = _create_requirement(
        client, record_id, class_id, subject_id, weekly_periods=3
    )

    # Sync to 3 lessons first.
    client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    # Shrink the requirement to 1 weekly period -- the existing 3 lessons
    # now exceed it.
    client.patch(
        f"/api/v1/class-subject-requirements/{requirement_id}",
        json={"weekly_periods": 1},
    )

    response = client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    assert response.status_code == 409
    over_provisioned = response.json()["over_provisioned"]
    assert len(over_provisioned) == 1
    assert over_provisioned[0]["class_subject_requirement_id"] == requirement_id
    assert over_provisioned[0]["weekly_periods"] == 1
    assert over_provisioned[0]["existing_lesson_count"] == 3

    # Nothing was auto-deleted.
    lessons_response = client.get("/api/v1/lessons/")
    assert len(lessons_response.json()) == 3


def test_generate_lessons_over_provisioned_flags_fixed_lesson(
    client: TestClient,
) -> None:
    """Task 28: if one of the Lessons that WOULD be considered "excess"
    (highest sequence_number) has a manually-set fixed_time_slot_id, the
    error must say so explicitly -- not treat it the same as an ordinary
    over-provisioning case."""
    record_id = _create_record(client, year=2077)
    class_id = _create_class(client, level=16)
    subject_id = _create_subject(client, name="Math 2077")
    requirement_id = _create_requirement(
        client, record_id, class_id, subject_id, weekly_periods=3
    )

    generate_response = client.post(
        f"/api/v1/schedule-versions/{record_id}/generate-lessons"
    )
    lessons = generate_response.json()["created_lessons"]
    # Fix the last-sequence lesson (sequence_number 3) to a specific slot.
    last_lesson = max(lessons, key=lambda lesson: lesson["sequence_number"])
    time_slot_id = create_time_slot(client, weekday=3, period=3)
    fix_response = client.patch(
        f"/api/v1/lessons/{last_lesson['lesson_id']}/fix-time-slot",
        json={"time_slot_id": time_slot_id},
    )
    assert fix_response.status_code == 200

    # Shrink the requirement to 1 weekly period -- lessons 2 and 3 (including
    # the fixed one) now count as "excess".
    client.patch(
        f"/api/v1/class-subject-requirements/{requirement_id}",
        json={"weekly_periods": 1},
    )

    response = client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    assert response.status_code == 409
    data = response.json()
    assert "已手動固定時段的課程" in data["detail"]
    over_provisioned = data["over_provisioned"]
    assert len(over_provisioned) == 1
    assert over_provisioned[0]["includes_fixed_lesson"] is True
    assert over_provisioned[0]["fixed_lesson_ids"] == [last_lesson["lesson_id"]]

    # Still nothing auto-deleted -- the fixed lesson (and its sibling) is
    # untouched, exactly like the ordinary over-provisioning case.
    lessons_response = client.get("/api/v1/lessons/")
    assert len(lessons_response.json()) == 3
    fixed_lesson_response = client.get(f"/api/v1/lessons/{last_lesson['lesson_id']}")
    assert fixed_lesson_response.json()["fixed_time_slot_id"] == time_slot_id


def test_generate_lessons_over_provisioned_without_fixed_lesson_has_no_extra_note(
    client: TestClient,
) -> None:
    """Regression guard: the ordinary over-provisioning case (Task 21) must
    not gain the Task 28 note when no fixed lesson is actually involved."""
    record_id = _create_record(client, year=2078)
    class_id = _create_class(client, level=17)
    subject_id = _create_subject(client, name="Math 2078")
    requirement_id = _create_requirement(
        client, record_id, class_id, subject_id, weekly_periods=3
    )
    client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")
    client.patch(
        f"/api/v1/class-subject-requirements/{requirement_id}",
        json={"weekly_periods": 1},
    )

    response = client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    assert response.status_code == 409
    data = response.json()
    assert "已手動固定時段的課程" not in data["detail"]
    assert data["over_provisioned"][0]["includes_fixed_lesson"] is False
    assert data["over_provisioned"][0]["fixed_lesson_ids"] == []


def test_generate_lessons_over_provisioned_blocks_other_requirements_too(
    client: TestClient,
) -> None:
    """One over-provisioned requirement aborts the WHOLE call atomically --
    a different, genuinely under-provisioned requirement of the same
    record gets nothing created either, in that same call."""
    record_id = _create_record(client, year=2079)
    class_id = _create_class(client, level=18)
    subject_a = _create_subject(client, name="Subject A 2079")
    subject_b = _create_subject(client, name="Subject B 2079")
    requirement_a = _create_requirement(
        client, record_id, class_id, subject_a, weekly_periods=2
    )
    _create_requirement(client, record_id, class_id, subject_b, weekly_periods=2)

    # Sync both requirements to 2 lessons each.
    client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    # Requirement A becomes over-provisioned.
    client.patch(
        f"/api/v1/class-subject-requirements/{requirement_a}",
        json={"weekly_periods": 1},
    )

    # A brand-new requirement C that genuinely needs lessons.
    subject_c = _create_subject(client, name="Subject C 2079")
    _create_requirement(client, record_id, class_id, subject_c, weekly_periods=2)

    response = client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    assert response.status_code == 409

    # Requirement C got nothing, even though it was legitimately short.
    lessons_response = client.get("/api/v1/lessons/")
    assert len(lessons_response.json()) == 4  # only the original 2 + 2


# --- v3: settings change only while a record is 尚未排課 ---


def test_generate_lessons_on_a_scheduled_record_returns_409(client: TestClient) -> None:
    record_id = _create_record(client, year=2080)
    class_id = _create_class(client, level=19)
    subject_id = _create_subject(client, name="Math 2080")
    _create_requirement(client, record_id, class_id, subject_id, weekly_periods=2)
    mark_status(client, record_id, "AUTO")

    response = client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")

    assert response.status_code == 409
    assert "尚未排課" in response.json()["detail"]
    assert client.get("/api/v1/lessons/").json() == []


def test_run_scheduler_on_a_scheduled_record_returns_409(client: TestClient) -> None:
    record_id = _create_record(client, year=2081)
    class_id = _create_class(client, level=20)
    subject_id = _create_subject(client, name="Math 2081")
    _create_requirement(client, record_id, class_id, subject_id, weekly_periods=1)
    client.post(f"/api/v1/schedule-versions/{record_id}/generate-lessons")
    mark_status(client, record_id, "MANUAL")

    response = client.post(f"/api/v1/schedule-versions/{record_id}/run-scheduler")

    # No Schedule rows exist, so the 409 can only come from the status.
    assert response.status_code == 409
    assert client.get("/api/v1/schedules/").json() == []


# --- Task 43: TEACHER may only see published records ---


def test_teacher_sees_only_published_versions_in_list(
    client: TestClient, teacher_client: TestClient
) -> None:
    semester_id = _create_semester(client, year=2082)
    draft_id = create_record(client, semester_id)
    published_id = create_record(client, semester_id)
    mark_status(client, published_id, "AUTO", is_published=True)

    response = teacher_client.get("/api/v1/schedule-versions/")

    assert response.status_code == 200
    version_ids = [version["id"] for version in response.json()]
    assert published_id in version_ids
    assert draft_id not in version_ids


def test_teacher_cannot_get_unpublished_version_by_id(
    client: TestClient, teacher_client: TestClient
) -> None:
    record_id = _create_record(client, year=2083)
    mark_status(client, record_id, "AUTO")

    # Same 404 a nonexistent id would get -- an unpublished record simply
    # isn't visible to TEACHER, not a separate "forbidden" response.
    response = teacher_client.get(f"/api/v1/schedule-versions/{record_id}")

    assert response.status_code == 404


def test_teacher_can_get_published_version_by_id(
    client: TestClient, teacher_client: TestClient
) -> None:
    record_id = _create_record(client, year=2084)
    mark_status(client, record_id, "AUTO", is_published=True)

    response = teacher_client.get(f"/api/v1/schedule-versions/{record_id}")

    assert response.status_code == 200
    assert response.json()["id"] == record_id


def test_teacher_cannot_create_or_change_records(
    client: TestClient, teacher_client: TestClient
) -> None:
    semester_id = _create_semester(client, year=2085)
    record_id = create_record(client, semester_id)

    assert teacher_client.post(
        "/api/v1/schedule-versions/", json={"semester_id": semester_id}
    ).status_code == 403
    assert teacher_client.patch(
        f"/api/v1/schedule-versions/{record_id}", json={"note": "x"}
    ).status_code == 403
    assert teacher_client.delete(f"/api/v1/schedule-versions/{record_id}").status_code == 403


# --- deleting: a record goes with everything it owns ---


def test_delete_record_takes_its_settings_and_timetable_with_it(
    client: TestClient,
) -> None:
    record_id = _create_record(client, year=2120)
    class_id = _create_class(client, level=50)
    subject_id = _create_subject(client, name="Subject 2120")
    requirement_id = _create_requirement(
        client, record_id, class_id, subject_id, weekly_periods=1
    )
    generate_response = client.post(
        f"/api/v1/schedule-versions/{record_id}/generate-lessons"
    )
    lesson_id = generate_response.json()["created_lessons"][0]["lesson_id"]
    mark_status(client, record_id, "EDITING")
    schedule_id = client.post(
        "/api/v1/schedules/",
        json={"schedule_version_id": record_id, "lesson_id": lesson_id},
    ).json()["id"]
    mark_status(client, record_id, "MANUAL")

    response = client.delete(f"/api/v1/schedule-versions/{record_id}")

    assert response.status_code == 204
    assert client.get(f"/api/v1/schedule-versions/{record_id}").status_code == 404
    assert client.get(f"/api/v1/class-subject-requirements/{requirement_id}").status_code == 404
    db = db_of(client)
    assert db.get(Lesson, lesson_id) is None
    assert db.get(Schedule, schedule_id) is None


def test_delete_record_takes_its_working_copies_with_it(client: TestClient) -> None:
    record_id = _create_record(client, year=2122)
    mark_status(client, record_id, "AUTO")
    working_copy = client.post(f"/api/v1/schedule-versions/{record_id}/edit").json()

    assert client.delete(f"/api/v1/schedule-versions/{record_id}").status_code == 204

    assert client.get(f"/api/v1/schedule-versions/{working_copy['id']}").status_code == 404


def test_delete_published_schedule_version_returns_409(client: TestClient) -> None:
    record_id = _create_record(client, year=2121)
    mark_status(client, record_id, "AUTO", is_published=True)

    response = client.delete(f"/api/v1/schedule-versions/{record_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "已發布的排課紀錄無法刪除"
    assert client.get(f"/api/v1/schedule-versions/{record_id}").status_code == 200
