from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.grade_class import Grade
from app.schemas.grade import GradeCreate, GradeRead, GradeUpdate
from app.services import grade as grade_service
from app.services import semester_settings as semester_settings_service

router = APIRouter(
    prefix="/api/v1/grades",
    tags=["grades"],
    dependencies=[Depends(require_school_member)],
)


@router.post("/", response_model=GradeRead, status_code=status.HTTP_201_CREATED)
def create_grade(
    grade_data: GradeCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Grade:
    return grade_service.create_grade(db, grade_data, school_id=school_id)


@router.get("/", response_model=list[GradeRead])
def list_grades(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[Grade]:
    return grade_service.get_grades(db, skip=skip, limit=limit, school_id=school_id)


@router.get("/{grade_id}", response_model=GradeRead)
def get_grade(
    grade_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> Grade:
    grade = grade_service.get_grade(db, grade_id, school_id=school_id)
    if grade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grade not found"
        )
    return grade


@router.get("/{grade_id}/default-time-slots", response_model=list[int])
def get_default_time_slots(
    grade_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[int]:
    """Task 98: the school's time slots this grade is open for by default
    (wizard step 8): 低年級 Tuesday 0-8 / other days 0-5, 中年級 Wednesday
    and Friday 0-5 / other days 0-8, 高年級 Wednesday 0-5 / other days 0-8,
    國中 every day 0-8 -- teaching periods only."""
    slot_ids = semester_settings_service.default_grade_time_slots(
        db, grade_id, school_id=school_id
    )
    if slot_ids is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grade not found"
        )
    return slot_ids


@router.patch("/{grade_id}", response_model=GradeRead)
def update_grade(
    grade_id: int,
    grade_data: GradeUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Grade:
    grade = grade_service.update_grade(db, grade_id, grade_data, school_id=school_id)
    if grade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grade not found"
        )
    return grade


@router.delete("/{grade_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grade(
    grade_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> None:
    deleted = grade_service.delete_grade(db, grade_id, school_id=school_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grade not found"
        )
