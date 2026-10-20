from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.teacher import Teacher


class TimeSlot(TimestampMixin, Base):
    __tablename__ = "time_slots"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 5", name="ck_time_slots_weekday_valid"),
        UniqueConstraint(
            "school_id", "weekday", "period", name="uq_time_slots_school_weekday_period"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Task 98: the school this row belongs to. Every query a 教學組長 or
    # 一般老師 makes is limited to their own school (app/services/school_scope.py).
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    # Weekday convention: 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday.
    weekday: Mapped[int] = mapped_column()
    # A school's grid is built with the school (國小 0-9, 國中/高中 0-10,
    # app/services/school_structure.py) and never grows or shrinks: only
    # label and is_teaching_period are editable.
    period: Mapped[int] = mapped_column()
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
