from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.academic_year import AcademicYear
from app.schemas.academic_year import (
    AcademicYearCreate,
    AcademicYearRead,
    AcademicYearUpdate,
)
from app.services import academic_year as academic_year_service

router = APIRouter(
    prefix="/api/v1/academic-years",
    tags=["academic_years"],
    dependencies=[Depends(require_school_member)],
)


@router.post("/", response_model=AcademicYearRead, status_code=status.HTTP_201_CREATED)
def create_academic_year(
    academic_year_data: AcademicYearCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> AcademicYear:
    return academic_year_service.create_academic_year(
        db, academic_year_data, school_id=school_id
    )


@router.get("/", response_model=list[AcademicYearRead])
def list_academic_years(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[AcademicYear]:
    return academic_year_service.get_academic_years(
        db, skip=skip, limit=limit, school_id=school_id
    )


@router.get("/{academic_year_id}", response_model=AcademicYearRead)
def get_academic_year(
    academic_year_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> AcademicYear:
    academic_year = academic_year_service.get_academic_year(
        db, academic_year_id, school_id=school_id
    )
    if academic_year is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AcademicYear not found"
        )
    return academic_year


@router.patch("/{academic_year_id}", response_model=AcademicYearRead)
def update_academic_year(
    academic_year_id: int,
    academic_year_data: AcademicYearUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> AcademicYear:
    academic_year = academic_year_service.update_academic_year(
        db, academic_year_id, academic_year_data, school_id=school_id
    )
    if academic_year is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AcademicYear not found"
        )
    return academic_year


@router.delete("/{academic_year_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_academic_year(
    academic_year_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> None:
    deleted = academic_year_service.delete_academic_year(
        db, academic_year_id, school_id=school_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AcademicYear not found"
        )
