from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.teacher import Teacher


class TimeSlot(TimestampMixin, Base):
    __tablename__ = "time_slots"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 5", name="ck_time_slots_weekday_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Weekday convention: 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday.
    weekday: Mapped[int] = mapped_column()
    period: Mapped[int] = mapped_column()
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_teaching_period: Mapped[bool] = mapped_column(default=True)

    unavailable_teachers: Mapped[list["Teacher"]] = relationship(
        secondary="teacher_availabilities",
        back_populates="unavailable_slots",
        viewonly=True,
    )
