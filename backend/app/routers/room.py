from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomRead, RoomUpdate
from app.services import room as room_service

router = APIRouter(prefix="/api/v1/rooms", tags=["rooms"])


@router.post("/", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room(room_data: RoomCreate, db: Session = Depends(get_db)) -> Room:
    return room_service.create_room(db, room_data)


@router.get("/", response_model=list[RoomRead])
def list_rooms(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[Room]:
    return room_service.get_rooms(db, skip=skip, limit=limit)


@router.get("/{room_id}", response_model=RoomRead)
def get_room(room_id: int, db: Session = Depends(get_db)) -> Room:
    room = room_service.get_room(db, room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    return room


@router.patch("/{room_id}", response_model=RoomRead)
def update_room(
    room_id: int, room_data: RoomUpdate, db: Session = Depends(get_db)
) -> Room:
    room = room_service.update_room(db, room_id, room_data)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    return room


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(room_id: int, db: Session = Depends(get_db)) -> None:
    deleted = room_service.delete_room(db, room_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
