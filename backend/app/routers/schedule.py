from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.services import schedule as schedule_service

router = APIRouter(
    prefix="/api/v1/schedules",
    tags=["schedules"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_schedule(
    schedule_data: ScheduleCreate, db: Session = Depends(get_db)
) -> Schedule:
    return schedule_service.create_schedule(db, schedule_data)


@router.get("/", response_model=list[ScheduleRead])
def list_schedules(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[Schedule]:
    return schedule_service.get_schedules(db, skip=skip, limit=limit)


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)) -> Schedule:
    schedule = schedule_service.get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
    return schedule


@router.patch(
    "/{schedule_id}",
    response_model=ScheduleRead,
    dependencies=[Depends(require_admin)],
)
def update_schedule(
    schedule_id: int, schedule_data: ScheduleUpdate, db: Session = Depends(get_db)
) -> Schedule:
    schedule = schedule_service.update_schedule(db, schedule_id, schedule_data)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
    return schedule


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)) -> None:
    deleted = schedule_service.delete_schedule(db, schedule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
