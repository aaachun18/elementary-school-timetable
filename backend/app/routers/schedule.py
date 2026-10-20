from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.services import schedule as schedule_service

router = APIRouter(
    prefix="/api/v1/schedules",
    tags=["schedules"],
    dependencies=[Depends(require_school_member)],
)


@router.post("/", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    schedule_data: ScheduleCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Schedule:
    return schedule_service.create_schedule(db, schedule_data, school_id=school_id)


@router.get("/", response_model=list[ScheduleRead])
def list_schedules(
    skip: int = 0,
    limit: int = 100,
    schedule_version_id: int | None = None,
    current_user: User = Depends(require_school_member),
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[Schedule]:
    # Task 43: TEACHER only ever sees Schedule rows belonging to a
    # PUBLISHED ScheduleVersion -- see schedule_version.py's own comment
    # on why this is a silent filter, not a 403. Task 66: the same holds
    # with schedule_version_id -- a hidden or missing version is an empty
    # list, not a 404.
    return schedule_service.get_schedules(
        db,
        skip=skip,
        limit=limit,
        schedule_version_id=schedule_version_id,
        role=current_user.role,
        school_id=school_id,
    )


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(
    schedule_id: int,
    current_user: User = Depends(require_school_member),
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> Schedule:
    schedule = schedule_service.get_schedule(
        db, schedule_id, role=current_user.role, school_id=school_id
    )
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Schedule:
    schedule = schedule_service.update_schedule(
        db, schedule_id, schedule_data, school_id=school_id
    )
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> None:
    deleted = schedule_service.delete_schedule(db, schedule_id, school_id=school_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
