from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # Plain string for now (e.g. "普通教室", "自然教室") -- see report for the
    # Enum-vs-string discussion; not decided unilaterally.
    room_type: Mapped[str] = mapped_column(String(100))
    # Optional per the initial spec review (H10 Room Capacity deferred):
    # kept so the constraint can be enabled later without a schema change.
    capacity: Mapped[int | None] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
