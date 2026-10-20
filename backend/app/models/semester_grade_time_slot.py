from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.academic_year import Semester
    from app.models.grade_class import Grade
    from app.models.time_slot import TimeSlot


class SemesterGradeTimeSlot(TimestampMixin, Base):
    """Task 98: a time slot a grade's classes may be scheduled in during one
    semester (wizard step 8). A row's existence means allowed; a slot with
    no row is closed to that grade (the engine enforces it as a Hard
    Constraint in a later Task). Kept per semester, like the teachers'
    settings, so changing it never re-judges an older semester's
    timetable."""

    __tablename__ = "semester_grade_time_slots"
    __table_args__ = (
        UniqueConstraint(
            "semester_id",
            "grade_id",
            "time_slot_id",
            name="uq_semester_grade_time_slot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"))
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id"))

    semester: Mapped["Semester"] = relationship()
    grade: Mapped["Grade"] = relationship()
    time_slot: Mapped["TimeSlot"] = relationship()
