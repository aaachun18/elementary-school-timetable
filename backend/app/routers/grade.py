from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.grade_class import Grade
from app.schemas.grade import GradeCreate, GradeRead, GradeUpdate
from app.services import grade as grade_service

router = APIRouter(
    prefix="/api/v1/grades",
    tags=["grades"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/",
    response_model=GradeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_grade(grade_data: GradeCreate, db: Session = Depends(get_db)) -> Grade:
    return grade_service.create_grade(db, grade_data)


@router.get("/", response_model=list[GradeRead])
def list_grades(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[Grade]:
    return grade_service.get_grades(db, skip=skip, limit=limit)


@router.get("/{grade_id}", response_model=GradeRead)
def get_grade(grade_id: int, db: Session = Depends(get_db)) -> Grade:
    grade = grade_service.get_grade(db, grade_id)
    if grade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grade not found"
        )
    return grade


@router.patch(
    "/{grade_id}", response_model=GradeRead, dependencies=[Depends(require_admin)]
)
def update_grade(
    grade_id: int, grade_data: GradeUpdate, db: Session = Depends(get_db)
) -> Grade:
    grade = grade_service.update_grade(db, grade_id, grade_data)
    if grade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grade not found"
        )
    return grade


@router.delete(
    "/{grade_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_grade(grade_id: int, db: Session = Depends(get_db)) -> None:
    deleted = grade_service.delete_grade(db, grade_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grade not found"
        )
