from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.subject import Subject
    from app.models.time_slot import TimeSlot


class Teacher(TimestampMixin, Base):
    __tablename__ = "teachers"
    __table_args__ = (
        CheckConstraint(
            "min_weekly_periods <= max_weekly_periods",
            name="ck_teachers_weekly_periods_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)
    min_weekly_periods: Mapped[int] = mapped_column()
    max_weekly_periods: Mapped[int] = mapped_column()

    # Read-only convenience views onto the association tables below. Writes
    # go through TeacherSubject / TeacherAvailability directly (they are the
    # actual queryable/insertable resources, e.g. for H5 / H4 checks).
    qualified_subjects: Mapped[list["Subject"]] = relationship(
        secondary="teacher_subjects",
        back_populates="qualified_teachers",
        viewonly=True,
    )
    unavailable_slots: Mapped[list["TimeSlot"]] = relationship(
        secondary="teacher_availabilities",
        back_populates="unavailable_teachers",
        viewonly=True,
    )


class TeacherSubject(TimestampMixin, Base):
    """A teacher's qualification to teach a subject (H5). Existence of a row
    means qualified; it does not mean the teacher is actually assigned to
    teach it (that is TeacherClassAssignment, a later Task)."""

    __tablename__ = "teacher_subjects"
    __table_args__ = (
        UniqueConstraint("teacher_id", "subject_id", name="uq_teacher_subject"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))

    teacher: Mapped["Teacher"] = relationship()
    subject: Mapped["Subject"] = relationship()


class TeacherAvailability(TimestampMixin, Base):
    """A time slot a teacher is NOT available for (H4). A row's existence
    means unavailable; no row means available (no is_available column)."""

    __tablename__ = "teacher_availabilities"
    __table_args__ = (
        UniqueConstraint("teacher_id", "time_slot_id", name="uq_teacher_timeslot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id"))

    teacher: Mapped["Teacher"] = relationship()
    time_slot: Mapped["TimeSlot"] = relationship()
