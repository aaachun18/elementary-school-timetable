from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.academic_year import Semester


class ScheduleVersion(TimestampMixin, Base):
    """A named attempt at scheduling a semester's lessons. DRAFT versions
    can be freely regenerated/edited; PUBLISHED ones are the authoritative
    timetable. Scheduling *results* (Schedule rows) belong to a specific
    version; the *requirement* list (Lesson) does not."""

    __tablename__ = "schedule_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED')", name="ck_schedule_versions_status_valid"
        ),
        UniqueConstraint(
            "semester_id",
            "version_number",
            name="uq_schedule_version_semester_number",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    version_number: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))

    semester: Mapped["Semester"] = relationship()
