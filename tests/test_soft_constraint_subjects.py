"""Which subjects the soft constraints are about (services/scheduler.py
soft_constraint_subjects()): found by words in the subject's name, since
schools name their subjects a little differently."""

from sqlalchemy.orm import Session

from app.models.school import School
from app.models.subject import Subject
from app.services.scheduler import soft_constraint_subjects


def _school_with_subjects(db_session: Session, school_type: str, names: list[str]) -> tuple[int, dict[str, int]]:
    school = School(name=f"{school_type} 測試學校", is_active=True, school_type=school_type)
    db_session.add(school)
    db_session.flush()
    subjects = [Subject(school_id=school.id, name=name, is_active=True) for name in names]
    db_session.add_all(subjects)
    db_session.commit()
    return school.id, {subject.name: subject.id for subject in subjects}


NAMES = ["國語文", "國文", "數學", "英文", "社會", "自然科學", "本土語文／臺灣手語", "健康與體育", "藝術", "綜合活動", "國際視野"]


def test_subjects_are_found_by_words_in_their_names(db_session: Session) -> None:
    school_id, ids = _school_with_subjects(db_session, "ELEMENTARY", NAMES)

    soft = soft_constraint_subjects(db_session, school_id)

    assert soft.preferred == {ids["國語文"], ids["國文"], ids["數學"]}
    assert soft.avoided == {ids["健康與體育"]}
    assert soft.activity == {ids["健康與體育"], ids["藝術"], ids["綜合活動"], ids["國際視野"]}


def test_activity_subjects_are_for_elementary_schools_only(db_session: Session) -> None:
    school_id, ids = _school_with_subjects(db_session, "JUNIOR_HIGH", NAMES)

    soft = soft_constraint_subjects(db_session, school_id)

    assert soft.activity == frozenset()
    assert soft.avoided == {ids["健康與體育"]}
