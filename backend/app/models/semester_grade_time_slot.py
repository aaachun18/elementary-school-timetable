from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.grade_class import Grade
    from app.models.schedule_version import ScheduleVersion
    from app.models.time_slot import TimeSlot


class SemesterGradeTimeSlot(TimestampMixin, Base):
    """Task 98: a time slot a grade's classes may be scheduled in (wizard
    step 年級與可排節次). A row's existence means allowed; a slot with no row
    is closed to that grade (H13). v3: part of one 排課紀錄's settings
    (schedule_version_id), like the teachers', so changing one record's
    never re-judges another's timetable."""

    __tablename__ = "semester_grade_time_slots"
    __table_args__ = (
        UniqueConstraint(
            "schedule_version_id",
            "grade_id",
            "time_slot_id",
            name="uq_semester_grade_time_slot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_version_id: Mapped[int] = mapped_column(ForeignKey("schedule_versions.id"))
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"))
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id"))

    schedule_version: Mapped["ScheduleVersion"] = relationship()
    grade: Mapped["Grade"] = relationship()
    time_slot: Mapped["TimeSlot"] = relationship()
