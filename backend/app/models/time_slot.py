from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String, Time
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
    # Optional: Scheduling Engine constraints (H1-H12, S1-S7) all key off
    # weekday + period, never actual clock time. These exist only for
    # future timetable UI display.
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    is_teaching_period: Mapped[bool] = mapped_column(default=True)
    # Task 35: a human-readable name for this slot -- e.g. "早自習",
    # "午餐/午休" for non-teaching periods, so the timetable can show a
    # real row label instead of a bare period number. Nullable for both
    # kinds of slot (teaching periods usually don't need one; non-teaching
    # ones are encouraged to have one but it isn't enforced at the schema
    # level -- see TimetableView.tsx's fallback text for the null case).
    label: Mapped[str | None] = mapped_column(String(100))

    unavailable_teachers: Mapped[list["Teacher"]] = relationship(
        secondary="teacher_availabilities",
        back_populates="unavailable_slots",
        viewonly=True,
    )
