from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_room(db: Session, room_data: RoomCreate) -> Room:
    room = Room(
        name=room_data.name,
        room_type=room_data.room_type,
        capacity=room_data.capacity,
        is_active=True,
    )
    db.add(room)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(room)
    return room


def get_room(db: Session, room_id: int) -> Room | None:
    return db.get(Room, room_id)


def get_rooms(db: Session, skip: int = 0, limit: int = 100) -> list[Room]:
    stmt = select(Room).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_room(db: Session, room_id: int, room_data: RoomUpdate) -> Room | None:
    room = db.get(Room, room_id)
    if room is None:
        return None

    for field, value in room_data.model_dump(exclude_unset=True).items():
        setattr(room, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(room)
    return room


def delete_room(db: Session, room_id: int) -> bool:
    room = db.get(Room, room_id)
    if room is None:
        return False

    try:
        db.delete(room)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Room {room_id} cannot be deleted: other records still "
            "reference it."
        ) from exc

    return True
