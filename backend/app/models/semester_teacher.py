from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.academic_year import Semester
    from app.models.teacher import Teacher
    from app.models.time_slot import TimeSlot


class SemesterTeacher(TimestampMixin, Base):
    """Task 98: a teacher taking part in one semester's scheduling, with
    that semester's weekly periods range (wizard steps 4-5). A teacher with
    no row for a semester is not scheduled in it at all. Replaces the
    teacher-wide Teacher.min/max_weekly_periods for scheduling (the engine
    switches over in a later Task)."""

    __tablename__ = "semester_teachers"
    __table_args__ = (
        UniqueConstraint("semester_id", "teacher_id", name="uq_semester_teacher"),
        CheckConstraint(
            "min_weekly_periods >= 0", name="ck_semester_teachers_min_not_negative"
        ),
        CheckConstraint(
            "min_weekly_periods <= max_weekly_periods",
            name="ck_semester_teachers_periods_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    min_weekly_periods: Mapped[int] = mapped_column()
    max_weekly_periods: Mapped[int] = mapped_column()

    semester: Mapped["Semester"] = relationship()
    teacher: Mapped["Teacher"] = relationship()
    unavailabilities: Mapped[list["SemesterTeacherUnavailability"]] = relationship(
        back_populates="semester_teacher"
    )


class SemesterTeacherUnavailability(TimestampMixin, Base):
    """Task 98: a time slot a participating teacher can't teach in this
    semester (wizard step 6) -- the per-semester replacement for
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
