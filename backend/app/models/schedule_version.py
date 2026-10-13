from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.academic_year import Semester

# ScheduleVersion.status values (Task 64 added ARCHIVED).
DRAFT = "DRAFT"
PUBLISHED = "PUBLISHED"
ARCHIVED = "ARCHIVED"
# Both are fully locked: no field change, no Schedule change, no deletion.
# The only way to change one is to copy it into a new DRAFT.
LOCKED_STATUSES = frozenset({PUBLISHED, ARCHIVED})


class ScheduleVersion(TimestampMixin, Base):
    """A named attempt at scheduling a semester's lessons. DRAFT versions
    can be freely regenerated/edited; the semester's single PUBLISHED one is
    the authoritative timetable; ARCHIVED ones are previously published
    versions that a later publish replaced (Task 64) -- kept as history and
    publishable again. Scheduling *results* (Schedule rows) belong to a
    specific version; the *requirement* list (Lesson) does not."""

    __tablename__ = "schedule_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')",
            name="ck_schedule_versions_status_valid",
        ),
        UniqueConstraint(
            "semester_id",
            "version_number",
            name="uq_schedule_version_semester_number",
        ),
        # Task 64: at most one PUBLISHED version per semester, guaranteed by
        # the database itself, not only by the publish service.
        Index(
            "uq_schedule_versions_one_published_per_semester",
            "semester_id",
            unique=True,
            postgresql_where=text("status = 'PUBLISHED'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    version_number: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))

    semester: Mapped["Semester"] = relationship()
