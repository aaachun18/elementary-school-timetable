"""學校資料 > 科目需求: how many periods a week every class of a grade
needs of a subject. The wizard copies these into a semester's
ClassSubjectRequirement rows (class_subject_requirement.py
sync_semester_requirements()), so a change here reaches a semester the
next time its 科目需求 step is opened."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.grade_class import Grade
from app.models.grade_subject_requirement import GradeSubjectRequirement
from app.models.subject import Subject
from app.schemas.grade_subject_requirement import (
    GradeSubjectRequirementCreate,
    GradeSubjectRequirementUpdate,
)
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)


def create_grade_subject_requirement(
    db: Session, data: GradeSubjectRequirementCreate, *, school_id: int
) -> GradeSubjectRequirement:
    """The same grade and subject twice -> 409 (unique)."""
    ensure_references_in_school(
        db, school_id, [(Grade, data.grade_id), (Subject, data.subject_id)]
    )
    requirement = GradeSubjectRequirement(
        grade_id=data.grade_id,
        subject_id=data.subject_id,
        weekly_periods=data.weekly_periods,
    )
    db.add(requirement)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(requirement)
    return requirement


def get_grade_subject_requirements(
    db: Session, *, school_id: int, grade_id: int | None = None
) -> list[GradeSubjectRequirement]:
    stmt = select(GradeSubjectRequirement).where(
        in_school(GradeSubjectRequirement, school_id)
    )
    if grade_id is not None:
        stmt = stmt.where(GradeSubjectRequirement.grade_id == grade_id)
    stmt = stmt.order_by(GradeSubjectRequirement.grade_id, GradeSubjectRequirement.id)
    return list(db.scalars(stmt).all())


def update_grade_subject_requirement(
    db: Session,
    requirement_id: int,
    data: GradeSubjectRequirementUpdate,
    *,
    school_id: int,
) -> GradeSubjectRequirement | None:
    requirement = get_in_school(db, GradeSubjectRequirement, requirement_id, school_id)
    if requirement is None:
        return None

    requirement.weekly_periods = data.weekly_periods
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(requirement)
    return requirement


def delete_grade_subject_requirement(
    db: Session, requirement_id: int, *, school_id: int
) -> bool:
    requirement = get_in_school(db, GradeSubjectRequirement, requirement_id, school_id)
    if requirement is None:
        return False

    try:
        db.delete(requirement)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"GradeSubjectRequirement {requirement_id} cannot be deleted: "
            "other records still reference it."
        ) from exc

    return True
