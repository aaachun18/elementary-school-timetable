"""Regression: the wizard's 年級與可排節次 and 科目需求 steps write the record's
settings as soon as they open, and the same request could reach the backend
twice at once. Both requests then inserted the same rows and the second one
failed on the unique constraint (409「資料重複或違反欄位限制」), leaving the
step showing only that error. Settings writes now lock the record row first,
so a second request waits for the first and sees what it committed."""

import threading
import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.schedule_version import ScheduleVersion
from app.services.class_subject_requirement import sync_version_requirements
from app.services.semester_settings import replace_grade_time_slots
from tests.api_helpers import create_class, create_grade
from tests.conftest import TestSessionLocal, get_test_school_id, time_slot_at
from tests.test_grade_subject_requirement import _record, _rule, _subject

# Long enough for the second request to reach the row lock and wait there.
WAIT_SECONDS = 0.5


def _run_while_record_is_locked(record_id: int, first, second):  # type: ignore[no-untyped-def]
    """Session A takes the record's row lock, `second` starts in its own
    session (thread) and has to wait; then `first` runs in session A and
    commits. Returns (first's result, second's result or exception)."""
    outcome: dict[str, object] = {}
    session_a = TestSessionLocal()
    session_b = TestSessionLocal()
    try:
        record = session_a.get(ScheduleVersion, record_id)
        assert record is not None
        session_a.refresh(record, with_for_update=True)

        def run_second() -> None:
            try:
                outcome["second"] = second(session_b)
            except Exception as exc:  # reported to the test below
                outcome["second"] = exc

        thread = threading.Thread(target=run_second)
        thread.start()
        time.sleep(WAIT_SECONDS)
        assert thread.is_alive(), "the second request should wait for the record lock"
        first_result = first(session_a)
        thread.join(timeout=10)
        return first_result, outcome["second"]
    finally:
        session_a.close()
        session_b.close()


def test_two_syncs_at_once_both_succeed(client: TestClient, db_session: Session) -> None:
    grade_id = create_grade(client, level=1)
    create_class(client, grade_id, "一年甲班")
    _rule(client, grade_id, _subject(client, "國語文"), 6)
    record_id = _record(client)
    school_id = get_test_school_id(db_session)

    def sync(session: Session):  # type: ignore[no-untyped-def]
        return sync_version_requirements(session, record_id, school_id=school_id)

    first, second = _run_while_record_is_locked(record_id, sync, sync)

    assert first.created == 1
    # Not an IntegrityError: it waited, then found the requirement made.
    assert not isinstance(second, Exception), second
    assert second.created == 0


def test_two_grade_slot_saves_at_once_both_succeed(
    client: TestClient, db_session: Session
) -> None:
    grade_id = create_grade(client, level=1)
    slot_ids = [time_slot_at(db_session, 1, period).id for period in (1, 2)]
    db_session.commit()
    record_id = _record(client)
    school_id = get_test_school_id(db_session)

    def save(session: Session):  # type: ignore[no-untyped-def]
        return replace_grade_time_slots(
            session, record_id, grade_id, slot_ids, school_id=school_id
        )

    first, second = _run_while_record_is_locked(record_id, save, save)

    assert first.time_slot_ids == sorted(slot_ids)
    assert not isinstance(second, Exception), second
    assert second.time_slot_ids == sorted(slot_ids)
