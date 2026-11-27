from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.subject import Subject
from app.models.teacher import TeacherSubject
from app.schemas.subject import SubjectCreate, SubjectUpdate
from app.services.delete_guidance import subject_delete_steps
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.school_scope import get_in_school, in_school


def create_subject(
    db: Session,
    subject_data: SubjectCreate,
    *,
    school_id: int,
) -> Subject:
    subject = Subject(school_id=school_id, name=subject_data.name, is_active=True)
    db.add(subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(subject)
    return subject


def get_subject(db: Session, subject_id: int, *, school_id: int) -> Subject | None:
    return get_in_school(db, Subject, subject_id, school_id)


def get_subjects(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[Subject]:
    stmt = select(
        Subject
    ).where(in_school(Subject, school_id)).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_subject(
    db: Session, subject_id: int, subject_data: SubjectUpdate, *, school_id: int
) -> Subject | None:
    subject = get_in_school(db, Subject, subject_id, school_id)
    if subject is None:
        return None

    for field, value in subject_data.model_dump(exclude_unset=True).items():
        setattr(subject, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(subject)
    return subject


def delete_subject(db: Session, subject_id: int, *, school_id: int) -> bool:
    subject = get_in_school(db, Subject, subject_id, school_id)
    if subject is None:
        return False

    # Task 49: same reasoning as Task 48's delete_teacher() -- TeacherSubject
    # is a join entity between Teacher and Subject with no independent
    # meaning of its own ("qualified to teach a subject" stops meaning
    # anything once the subject itself is gone), and its FK to subjects.id
    # has no ON DELETE CASCADE, so without this ANY subject that was ever
    # given to a teacher as a qualification could never be deleted at all.
    # ClassSubjectRequirement.subject_id is deliberately left alone -- a
    # subject some class's requirement still needs must stay blocked.
    #
    # Everything below is staged on `db` but not committed yet -- if the
    # final commit() fails (a real ClassSubjectRequirement reference), the
    # rollback() undoes the whole transaction, including these deletes, so
    # no teacher's qualifications are lost on a failed delete attempt.
    qualifications = db.scalars(
        select(TeacherSubject).where(TeacherSubject.subject_id == subject_id)
    ).all()
    for qualification in qualifications:
        db.delete(qualification)

    db.delete(subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Subject {subject_id} cannot be deleted: other records still "
            "reference it.",
            subject_delete_steps(db, subject_id),
        ) from exc

    return True
