from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint(
            "max_classes BETWEEN 1 AND 10", name="ck_rooms_max_classes_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Task 98: the school this row belongs to. Every query a 教學組長 or
    # 一般老師 makes is limited to their own school (app/services/school_scope.py).
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(100))
    # Deprecated since Task 98: rooms have no type any more (a requirement
    # names its one room, ClassSubjectRequirement.required_room_id). Kept
    # (column and data) so nothing is lost; new rooms leave it empty.
    room_type: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)
    # How many classes may use the room at the same time (1-10). A combined
    # lesson (共同排課) counts as one, however many classes it has.
    max_classes: Mapped[int] = mapped_column(default=1, server_default="1")
