from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear, Semester
from app.schemas.semester import SemesterCreate, SemesterUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.semester_settings import delete_settings_of_semester
from app.services.school_scope import (
    ensure_references_in_school,
    get_in_school,
    in_school,
)


def create_semester(
    db: Session,
    semester_data: SemesterCreate,
    *,
    school_id: int,
) -> Semester:
    ensure_references_in_school(
        db, school_id, [(AcademicYear, semester_data.academic_year_id)]
    )
    semester = Semester(
        academic_year_id=semester_data.academic_year_id,
        number=semester_data.number,
        is_active=True,
    )
    db.add(semester)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(semester)
    return semester


def get_semester(db: Session, semester_id: int, *, school_id: int) -> Semester | None:
    return get_in_school(db, Semester, semester_id, school_id)


def get_semesters(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[Semester]:
    stmt = select(
        Semester
    ).where(in_school(Semester, school_id)).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_semester(
    db: Session, semester_id: int, semester_data: SemesterUpdate, *, school_id: int
) -> Semester | None:
    semester = get_in_school(db, Semester, semester_id, school_id)
    if semester is None:
        return None

    changes = semester_data.model_dump(exclude_unset=True)
    ensure_references_in_school(
        db, school_id, [(AcademicYear, changes.get("academic_year_id"))]
    )
    for field, value in changes.items():
        setattr(semester, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(semester)
    return semester


def delete_semester(db: Session, semester_id: int, *, school_id: int) -> bool:
    semester = get_in_school(db, Semester, semester_id, school_id)
    if semester is None:
        return False

    try:
        # Task 98: its scheduling settings are owned by it (a semester with
        # requirements or versions is still refused by their foreign keys).
        delete_settings_of_semester(db, semester_id)
        db.delete(semester)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Semester {semester_id} cannot be deleted: other records "
            "still reference it."
        ) from exc

    return True
