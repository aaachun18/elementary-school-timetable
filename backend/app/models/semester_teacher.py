from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.schedule_version import ScheduleVersion
    from app.models.teacher import Teacher
    from app.models.time_slot import TimeSlot


class SemesterTeacher(TimestampMixin, Base):
    """Task 98: a teacher taking part in a semester's scheduling, with that
    semester's weekly periods range (wizard step 教師設定). A teacher with no
    row is not scheduled at all. v3: part of one 排課紀錄's settings
    (schedule_version_id), so every record keeps its own teachers."""

    __tablename__ = "semester_teachers"
    __table_args__ = (
        UniqueConstraint("schedule_version_id", "teacher_id", name="uq_semester_teacher"),
        CheckConstraint(
            "min_weekly_periods >= 0", name="ck_semester_teachers_min_not_negative"
        ),
        CheckConstraint(
            "min_weekly_periods <= max_weekly_periods",
            name="ck_semester_teachers_periods_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_version_id: Mapped[int] = mapped_column(ForeignKey("schedule_versions.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    min_weekly_periods: Mapped[int] = mapped_column()
    max_weekly_periods: Mapped[int] = mapped_column()

    schedule_version: Mapped["ScheduleVersion"] = relationship()
    teacher: Mapped["Teacher"] = relationship()
    unavailabilities: Mapped[list["SemesterTeacherUnavailability"]] = relationship(
        back_populates="semester_teacher"
    )


class SemesterTeacherUnavailability(TimestampMixin, Base):
    """Task 98: a time slot a participating teacher can't teach in (wizard
    step 教師設定) -- the per-record replacement for
    TeacherAvailability (H4). A row's existence means unavailable. Hanging
    off SemesterTeacher means only a participating teacher can have one."""

    __tablename__ = "semester_teacher_unavailabilities"
    __table_args__ = (
        UniqueConstraint(
            "semester_teacher_id",
            "time_slot_id",
            name="uq_semester_teacher_unavailability",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_teacher_id: Mapped[int] = mapped_column(ForeignKey("semester_teachers.id"))
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id"))

    semester_teacher: Mapped["SemesterTeacher"] = relationship(
        back_populates="unavailabilities"
    )
    time_slot: Mapped["TimeSlot"] = relationship()
