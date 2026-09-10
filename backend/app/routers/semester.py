from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.academic_year import Semester
from app.schemas.semester import SemesterCreate, SemesterRead, SemesterUpdate
from app.services import semester as semester_service

router = APIRouter(
    prefix="/api/v1/semesters",
    tags=["semesters"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/",
    response_model=SemesterRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_semester(
    semester_data: SemesterCreate, db: Session = Depends(get_db)
) -> Semester:
    return semester_service.create_semester(db, semester_data)


@router.get("/", response_model=list[SemesterRead])
def list_semesters(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[Semester]:
    return semester_service.get_semesters(db, skip=skip, limit=limit)


@router.get("/{semester_id}", response_model=SemesterRead)
def get_semester(semester_id: int, db: Session = Depends(get_db)) -> Semester:
    semester = semester_service.get_semester(db, semester_id)
    if semester is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found"
        )
    return semester


@router.patch(
    "/{semester_id}",
    response_model=SemesterRead,
    dependencies=[Depends(require_admin)],
)
def update_semester(
    semester_id: int, semester_data: SemesterUpdate, db: Session = Depends(get_db)
) -> Semester:
    semester = semester_service.update_semester(db, semester_id, semester_data)
    if semester is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found"
        )
    return semester


@router.delete(
    "/{semester_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_semester(semester_id: int, db: Session = Depends(get_db)) -> None:
    deleted = semester_service.delete_semester(db, semester_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found"
        )
