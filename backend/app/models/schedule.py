from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.lesson import Lesson
    from app.models.room import Room
    from app.models.schedule_version import ScheduleVersion
    from app.models.teacher import Teacher
    from app.models.time_slot import TimeSlot


class Schedule(TimestampMixin, Base):
    """Where one Lesson actually landed on the timetable within one
    ScheduleVersion. teacher/time_slot/room start nullable -- the row can
    exist (e.g. from a partial manual placement) before every slot of the
    assignment is filled in; the scheduling algorithm and hard-constraint
    validation are out of scope for this Task."""

    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint(
            "schedule_version_id", "lesson_id", name="uq_schedule_version_lesson"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_version_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_versions.id")
    )
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"))
    time_slot_id: Mapped[int | None] = mapped_column(ForeignKey("time_slots.id"))
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"))

    schedule_version: Mapped["ScheduleVersion"] = relationship()
    lesson: Mapped["Lesson"] = relationship()
    teacher: Mapped["Teacher | None"] = relationship()
    time_slot: Mapped["TimeSlot | None"] = relationship()
    room: Mapped["Room | None"] = relationship()
