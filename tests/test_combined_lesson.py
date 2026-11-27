"""共同排課 (POST/PUT/DELETE /api/v1/combined-lessons): lessons of several
classes taught together. The rules (same weekly periods and pattern, whole
blocks, fixed slots that agree), what the scheduler does with them, and how
the rest of the record follows (sync, pattern edits, fixed slots, copies,
manual moves)."""

from fastapi.testclient import TestClient

from tests.api_helpers import (
    create_class,
    create_enrolled_teacher,
    create_grade,
    create_time_slot,
)
from tests.test_grade_subject_requirement import _record, _requirements, _rule, _subject, _sync

URL = "/api/v1/combined-lessons"
CSR = "/api/v1/class-subject-requirements"
RECORDS = "/api/v1/schedule-versions"


class _World:
    """一年甲班 and 二年甲班, both with 本土語文 (weekly `periods`) and 國語文
    (2), slots 1-6 of Monday, one teacher."""

    def __init__(self, client: TestClient, periods: int = 1, local_periods_b: int | None = None) -> None:
        self.client = client
        grade_1 = create_grade(client, level=1)
        grade_2 = create_grade(client, level=2)
        self.class_a = create_class(client, grade_1, "一年甲班")
        self.class_b = create_class(client, grade_2, "二年甲班")
        self.local = _subject(client, "本土語文")
        self.mandarin = _subject(client, "國語文")
        self.rule_a = _rule(client, grade_1, self.local, periods)
        self.rule_b = _rule(client, grade_2, self.local, local_periods_b or periods)
        _rule(client, grade_1, self.mandarin, 2)
        _rule(client, grade_2, self.mandarin, 2)
        self.slots = [create_time_slot(client, 1, period) for period in (1, 2, 3, 4, 5, 6)]
        self.record = _record(client)
        self.teacher = create_enrolled_teacher(client, self.record, "王老師")
        _sync(client, self.record)
        requirements = _requirements(client, self.record)
        self.req_a = requirements[(self.class_a, self.local)]
        self.req_b = requirements[(self.class_b, self.local)]

    def combine(self, **fields: object) -> dict:
        body = {
            "schedule_version_id": self.record,
            "requirement_ids": [self.req_a["id"], self.req_b["id"]],
            "merged_count": 1,
            **fields,
        }
        return self.client.post(f"{URL}/", json=body)  # type: ignore[return-value]

    def lessons_of(self, requirement_id: int) -> list[dict]:
        lessons = self.client.get(
            "/api/v1/lessons/", params={"schedule_version_id": self.record, "limit": 1000}
        ).json()
        return sorted(
            (lesson for lesson in lessons if lesson["class_subject_requirement_id"] == requirement_id),
            key=lambda lesson: lesson["sequence_number"],
        )


def test_combining_lines_up_one_lesson_of_each_class(client: TestClient) -> None:
    world = _World(client)

    response = world.combine()

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["requirement_ids"] == [world.req_a["id"], world.req_b["id"]]
    assert body["homeroom_class_id"] == world.class_a  # the class that started it
    [instance] = body["instances"]
    assert instance["member_lesson_ids"] == [
        [world.lessons_of(world.req_a["id"])[0]["id"]],
        [world.lessons_of(world.req_b["id"])[0]["id"]],
    ]
    listed = client.get(f"{URL}/", params={"schedule_version_id": world.record}).json()
    assert [item["id"] for item in listed] == [body["id"]]


def test_weekly_periods_must_match(client: TestClient) -> None:
    world = _World(client, periods=1, local_periods_b=2)

    response = world.combine()

    assert response.status_code == 422
    assert response.json()["detail"] == "只有每週節數相同的課才能合併"


def test_a_class_cannot_combine_with_itself(client: TestClient) -> None:
    world = _World(client)
    mandarin_a = _requirements(client, world.record)[(world.class_a, world.mandarin)]

    response = world.combine(requirement_ids=[world.req_a["id"], mandarin_a["id"]])

    assert response.status_code == 422


def test_a_requirement_is_in_one_combined_lesson_only(client: TestClient) -> None:
    world = _World(client)
    assert world.combine().status_code == 201

    response = world.combine()

    assert response.status_code == 422
    assert response.json()["detail"] == "其中有科目需求已經設定了其他共同排課"


def test_merged_count_cannot_exceed_weekly_periods(client: TestClient) -> None:
    world = _World(client, periods=2)

    assert world.combine(merged_count=3).status_code == 422
    response = world.combine(merged_count=2)
    assert response.status_code == 201
    assert len(response.json()["instances"]) == 2


def test_with_a_pattern_only_whole_blocks_merge(client: TestClient) -> None:
    world = _World(client, periods=3)
    for requirement in (world.req_a, world.req_b):
        client.patch(f"{CSR}/{requirement['id']}", json={"lesson_pattern": "2+1"})

    assert world.combine(block_nos=None).status_code == 422
    response = world.combine(block_nos=[1])

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["merged_count"] == 2
    [instance] = body["instances"]
    assert [len(lesson_ids) for lesson_ids in instance["member_lesson_ids"]] == [2, 2]


def test_patterns_must_match(client: TestClient) -> None:
    world = _World(client, periods=3)
    client.patch(f"{CSR}/{world.req_a['id']}", json={"lesson_pattern": "2+1"})

    response = world.combine(merged_count=1)

    assert response.status_code == 422
    assert response.json()["detail"] == "合併的課連堂樣式必須相同"


def test_a_combined_requirement_keeps_its_pattern(client: TestClient) -> None:
    world = _World(client, periods=2)
    assert world.combine().status_code == 201

    response = client.patch(f"{CSR}/{world.req_a['id']}", json={"lesson_pattern": "2"})

    assert response.status_code == 409


def test_fixed_slots_must_agree_and_one_fixes_the_others(client: TestClient) -> None:
    world = _World(client)
    client.post(f"{RECORDS}/{world.record}/generate-lessons")
    lesson_a = world.lessons_of(world.req_a["id"])[0]
    lesson_b = world.lessons_of(world.req_b["id"])[0]
    client.patch(f"/api/v1/lessons/{lesson_a['id']}/fix-time-slot", json={"time_slot_id": world.slots[0]})
    client.patch(f"/api/v1/lessons/{lesson_b['id']}/fix-time-slot", json={"time_slot_id": world.slots[1]})

    assert world.combine().status_code == 422

    client.patch(f"/api/v1/lessons/{lesson_b['id']}/fix-time-slot", json={"time_slot_id": None})
    assert world.combine().status_code == 201
    assert world.lessons_of(world.req_b["id"])[0]["fixed_time_slot_id"] == world.slots[0]

    # Changing one later changes the other.
    client.patch(f"/api/v1/lessons/{lesson_b['id']}/fix-time-slot", json={"time_slot_id": world.slots[2]})
    assert world.lessons_of(world.req_a["id"])[0]["fixed_time_slot_id"] == world.slots[2]


def test_the_scheduler_places_a_combined_lesson_as_one(client: TestClient) -> None:
    world = _World(client)
    assert world.combine().status_code == 201
    # One teacher, two classes, 2 x 國語文 + 1 本土語文 each: within a
    # maximum of 5 only because the 本土語文 of both classes is one lesson.
    client.put(
        f"{RECORDS}/{world.record}/teachers",
        json={"teachers": [{"teacher_id": world.teacher, "min_weekly_periods": 0, "max_weekly_periods": 5}]},
    )

    response = client.post(f"{RECORDS}/{world.record}/run-scheduler")

    assert response.status_code == 200, response.json()
    rows = client.get("/api/v1/schedules/", params={"limit": 1000}).json()
    lesson_a = world.lessons_of(world.req_a["id"])[0]["id"]
    lesson_b = world.lessons_of(world.req_b["id"])[0]["id"]
    by_lesson = {row["lesson_id"]: row for row in rows}
    assert by_lesson[lesson_a]["time_slot_id"] == by_lesson[lesson_b]["time_slot_id"]
    assert by_lesson[lesson_a]["teacher_id"] == by_lesson[lesson_b]["teacher_id"] == world.teacher
    check = client.get(f"{RECORDS}/{world.record}/check").json()
    assert [item for item in check["violations"] if item["severity"] == "ERROR"] == []


def test_resizing_a_member_in_the_school_data_drops_the_combined_lesson(client: TestClient) -> None:
    world = _World(client)
    assert world.combine().status_code == 201

    client.patch(f"/api/v1/grade-subject-requirements/{world.rule_a}", json={"weekly_periods": 2})
    _sync(client, world.record)

    assert client.get(f"{URL}/", params={"schedule_version_id": world.record}).json() == []


def test_copied_settings_keep_the_combined_lessons(client: TestClient) -> None:
    world = _World(client)
    assert world.combine().status_code == 201

    copy_id = client.post(f"{RECORDS}/{world.record}/copy-settings").json()["id"]

    [copied] = client.get(f"{URL}/", params={"schedule_version_id": copy_id}).json()
    copied_requirements = _requirements(client, copy_id)
    assert copied["requirement_ids"] == [
        copied_requirements[(world.class_a, world.local)]["id"],
        copied_requirements[(world.class_b, world.local)]["id"],
    ]


def test_update_and_delete(client: TestClient) -> None:
    world = _World(client)
    combined_id = world.combine().json()["id"]

    updated = client.put(
        f"{URL}/{combined_id}",
        json={
            "requirement_ids": [world.req_a["id"], world.req_b["id"]],
            "merged_count": 1,
            "homeroom_class_id": world.class_b,
        },
    )
    assert updated.status_code == 200, updated.json()
    assert updated.json()["homeroom_class_id"] == world.class_b

    assert client.delete(f"{URL}/{combined_id}").status_code == 204
    assert client.get(f"{URL}/", params={"schedule_version_id": world.record}).json() == []


def test_homeroom_must_be_a_member_class(client: TestClient) -> None:
    world = _World(client)
    other = create_class(client, create_grade(client, level=3), "三年甲班")

    response = world.combine(homeroom_class_id=other)

    assert response.status_code == 422


def test_moving_one_member_by_hand_moves_the_other(client: TestClient) -> None:
    world = _World(client)
    assert world.combine().status_code == 201
    assert client.post(f"{RECORDS}/{world.record}/run-scheduler").status_code == 200
    copy_id = client.post(f"{RECORDS}/{world.record}/edit").json()["id"]
    # The working copy has its own requirements, lessons and rows.
    copy_requirements = _requirements(client, copy_id)
    lesson_of_requirement = {
        lesson["class_subject_requirement_id"]: lesson["id"]
        for lesson in client.get(
            "/api/v1/lessons/", params={"schedule_version_id": copy_id, "limit": 1000}
        ).json()
    }
    rows = [
        row
        for row in client.get("/api/v1/schedules/", params={"limit": 1000}).json()
        if row["schedule_version_id"] == copy_id
    ]
    row_of_lesson = {row["lesson_id"]: row for row in rows}
    row_a = row_of_lesson[lesson_of_requirement[copy_requirements[(world.class_a, world.local)]["id"]]]
    row_b = row_of_lesson[lesson_of_requirement[copy_requirements[(world.class_b, world.local)]["id"]]]
    # The teacher teaches 5 of the 6 slots, so one is free for both classes.
    free = next(slot for slot in world.slots if slot not in {row["time_slot_id"] for row in rows})

    response = client.post(
        f"{RECORDS}/{copy_id}/move-lesson",
        json={"schedule_id": row_a["id"], "target_time_slot_id": free},
    )

    assert response.status_code == 200, response.json()
    changes = {change["schedule_id"]: change["new_time_slot_id"] for change in response.json()["changes"]}
    assert changes == {row_a["id"]: free, row_b["id"]: free}


def test_a_member_of_a_combined_lesson_cannot_be_unscheduled(client: TestClient) -> None:
    """移出課表: placing it back could not bring the other class's lesson
    with it, so a lesson of a 合併節 stays in the timetable."""
    world = _World(client)
    assert world.combine().status_code == 201
    assert client.post(f"{RECORDS}/{world.record}/run-scheduler").status_code == 200
    copy_id = client.post(f"{RECORDS}/{world.record}/edit").json()["id"]
    copy_requirements = _requirements(client, copy_id)
    lesson_of_requirement = {
        lesson["class_subject_requirement_id"]: lesson["id"]
        for lesson in client.get(
            "/api/v1/lessons/", params={"schedule_version_id": copy_id, "limit": 1000}
        ).json()
    }
    row_of_lesson = {
        row["lesson_id"]: row
        for row in client.get("/api/v1/schedules/", params={"limit": 1000}).json()
        if row["schedule_version_id"] == copy_id
    }
    row_a = row_of_lesson[lesson_of_requirement[copy_requirements[(world.class_a, world.local)]["id"]]]

    response = client.post(f"{RECORDS}/{copy_id}/unschedule-lesson", json={"schedule_id": row_a["id"]})

    assert response.status_code == 409, response.json()
    assert response.json()["reason"] == "UNSCHEDULE_COMBINED"
    assert response.json()["detail"] == "共同排課的課不能移出課表"
