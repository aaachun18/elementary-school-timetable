"""導師 (homeroom teachers): set per 排課紀錄 in the wizard's 教師設定 step
(SemesterTeacher.homeroom_class_id), one class per teacher and one 導師 per
class. At a 國小 the 導師 teaches the class's 國語文 and 數學 by default
(services/homeroom.py); 國中 / 高中 have no such default."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.school import School
from tests.api_helpers import create_class, create_grade, create_teacher
from tests.conftest import get_test_school_id
from tests.test_grade_subject_requirement import _record, _requirements, _rule, _subject, _sync

CSR = "/api/v1/class-subject-requirements"


def _teachers_url(record_id: int) -> str:
    return f"/api/v1/schedule-versions/{record_id}/teachers"


def _entry(teacher_id: int, homeroom_class_id: int | None = None) -> dict:
    return {
        "teacher_id": teacher_id,
        "min_weekly_periods": 0,
        "max_weekly_periods": 20,
        "unavailable_time_slot_ids": [],
        "homeroom_class_id": homeroom_class_id,
    }


def _put_teachers(client: TestClient, record_id: int, entries: list[dict]) -> None:
    response = client.put(_teachers_url(record_id), json={"teachers": entries})
    assert response.status_code == 200, response.json()


class _World:
    def __init__(self, client: TestClient) -> None:
        grade_id = create_grade(client, level=1)
        self.class_a = create_class(client, grade_id, "一年甲班")
        self.class_b = create_class(client, grade_id, "一年乙班")
        self.mandarin = _subject(client, "國語文")
        self.math = _subject(client, "數學")
        self.music = _subject(client, "藝術")
        for subject_id, periods in ((self.mandarin, 6), (self.math, 4), (self.music, 3)):
            _rule(client, grade_id, subject_id, periods)
        self.record = _record(client)
        self.wang = create_teacher(client, "王老師")
        self.lee = create_teacher(client, "李老師")


def _teacher_of(client: TestClient, world: _World, class_id: int, subject_id: int) -> int | None:
    teacher_id: int | None = _requirements(client, world.record)[(class_id, subject_id)][
        "required_teacher_id"
    ]
    return teacher_id


def test_homeroom_is_saved_and_read_back(client: TestClient) -> None:
    world = _World(client)

    _put_teachers(client, world.record, [_entry(world.wang, world.class_a), _entry(world.lee)])

    rows = {row["teacher_id"]: row for row in client.get(_teachers_url(world.record)).json()}
    assert rows[world.wang]["homeroom_class_id"] == world.class_a
    assert rows[world.lee]["homeroom_class_id"] is None


def test_a_class_has_at_most_one_homeroom_teacher(client: TestClient) -> None:
    world = _World(client)

    response = client.put(
        _teachers_url(world.record),
        json={"teachers": [_entry(world.wang, world.class_a), _entry(world.lee, world.class_a)]},
    )

    assert response.status_code == 422
    assert client.get(_teachers_url(world.record)).json() == []


def test_homeroom_class_must_exist_in_the_school(client: TestClient) -> None:
    world = _World(client)

    response = client.put(
        _teachers_url(world.record), json={"teachers": [_entry(world.wang, 999999)]}
    )

    assert response.status_code == 422


def test_elementary_homeroom_teaches_mandarin_and_math_once_synced(client: TestClient) -> None:
    world = _World(client)
    _put_teachers(client, world.record, [_entry(world.wang, world.class_a), _entry(world.lee)])

    _sync(client, world.record)

    assert _teacher_of(client, world, world.class_a, world.mandarin) == world.wang
    assert _teacher_of(client, world, world.class_a, world.math) == world.wang
    assert _teacher_of(client, world, world.class_a, world.music) is None
    # 一年乙班 has no 導師 yet.
    assert _teacher_of(client, world, world.class_b, world.mandarin) is None


def test_setting_a_homeroom_later_updates_existing_requirements(client: TestClient) -> None:
    world = _World(client)
    _put_teachers(client, world.record, [_entry(world.wang), _entry(world.lee)])
    _sync(client, world.record)
    music_id = _requirements(client, world.record)[(world.class_b, world.music)]["id"]
    client.patch(f"{CSR}/{music_id}", json={"required_teacher_id": world.lee})

    _put_teachers(client, world.record, [_entry(world.wang), _entry(world.lee, world.class_b)])

    assert _teacher_of(client, world, world.class_b, world.mandarin) == world.lee
    assert _teacher_of(client, world, world.class_b, world.math) == world.lee
    # Not a 導師 subject: untouched.
    assert _teacher_of(client, world, world.class_b, world.music) == world.lee
    assert _teacher_of(client, world, world.class_a, world.mandarin) is None


def test_changing_the_homeroom_moves_the_default_subjects(client: TestClient) -> None:
    world = _World(client)
    _put_teachers(client, world.record, [_entry(world.wang, world.class_a), _entry(world.lee)])
    _sync(client, world.record)

    _put_teachers(client, world.record, [_entry(world.wang), _entry(world.lee, world.class_a)])

    assert _teacher_of(client, world, world.class_a, world.mandarin) == world.lee
    assert _teacher_of(client, world, world.class_a, world.math) == world.lee


def test_removing_the_homeroom_clears_only_what_it_set(client: TestClient) -> None:
    world = _World(client)
    _put_teachers(client, world.record, [_entry(world.wang, world.class_a), _entry(world.lee)])
    _sync(client, world.record)
    math_id = _requirements(client, world.record)[(world.class_a, world.math)]["id"]
    client.patch(f"{CSR}/{math_id}", json={"required_teacher_id": world.lee})

    _put_teachers(client, world.record, [_entry(world.wang), _entry(world.lee)])

    assert _teacher_of(client, world, world.class_a, world.mandarin) is None
    # Changed by hand in the 科目需求 step: kept.
    assert _teacher_of(client, world, world.class_a, world.math) == world.lee


def test_a_teacher_chosen_in_the_requirements_step_survives_a_resync(client: TestClient) -> None:
    world = _World(client)
    _put_teachers(client, world.record, [_entry(world.wang, world.class_a), _entry(world.lee)])
    _sync(client, world.record)
    mandarin_id = _requirements(client, world.record)[(world.class_a, world.mandarin)]["id"]
    client.patch(f"{CSR}/{mandarin_id}", json={"required_teacher_id": world.lee})

    _sync(client, world.record)
    # Saving the same 導師 again changes nothing either.
    _put_teachers(client, world.record, [_entry(world.wang, world.class_a), _entry(world.lee)])

    assert _teacher_of(client, world, world.class_a, world.mandarin) == world.lee


def test_junior_high_homeroom_has_no_default_subjects(
    client: TestClient, db_session: Session
) -> None:
    world = _World(client)
    school = db_session.scalars(
        select(School).where(School.id == get_test_school_id(db_session))
    ).one()
    school.school_type = "JUNIOR_HIGH"
    db_session.commit()
    _put_teachers(client, world.record, [_entry(world.wang, world.class_a), _entry(world.lee)])

    _sync(client, world.record)

    assert _teacher_of(client, world, world.class_a, world.mandarin) is None
    assert _teacher_of(client, world, world.class_a, world.math) is None


def test_copied_settings_keep_the_homerooms(client: TestClient) -> None:
    world = _World(client)
    _put_teachers(client, world.record, [_entry(world.wang, world.class_a), _entry(world.lee)])

    response = client.post(f"/api/v1/schedule-versions/{world.record}/copy-settings")

    assert response.status_code in (200, 201), response.json()
    copy_id = response.json()["id"]
    rows = {row["teacher_id"]: row for row in client.get(_teachers_url(copy_id)).json()}
    assert rows[world.wang]["homeroom_class_id"] == world.class_a
