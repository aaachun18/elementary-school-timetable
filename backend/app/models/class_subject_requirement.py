from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.grade_class import Class
    from app.models.room import Room
    from app.models.schedule_version import ScheduleVersion
    from app.models.subject import Subject
    from app.models.teacher import Teacher


class ClassSubjectRequirement(TimestampMixin, Base):
    """How many weekly periods a class needs of a subject (and optional
    constraints on who/where), independent of whether any Lesson has
    actually been scheduled for it yet. v3: part of one 排課紀錄's settings
    (schedule_version_id) -- the semester is the record's."""

    __tablename__ = "class_subject_requirements"
    __table_args__ = (
        UniqueConstraint(
            "schedule_version_id",
            "class_id",
            "subject_id",
            name="uq_class_subject_requirement",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_version_id: Mapped[int] = mapped_column(ForeignKey("schedule_versions.id"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    weekly_periods: Mapped[int] = mapped_column()
    required_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.id")
    )
    required_room_type: Mapped[str | None] = mapped_column(String(100))
    # Deprecated since Task 87: no rule reads it any more -- replaced by
    # lesson_pattern. Kept (column and data) so nothing is lost.
    consecutive_limit: Mapped[int | None] = mapped_column()
    # Task 87: how weekly_periods is split into blocks of consecutive
    # lessons, e.g. "2+1" (canonical form: largest block first, see
    # app/services/lesson_pattern.py). None = no pattern: lessons are
    # independent, exactly as before.
    lesson_pattern: Mapped[str | None] = mapped_column(String(20))
    # Task 98: the one special room this subject is taught in (wizard step
    # 13). None = 原班上課, no school room (課表上不顯示). Replaces
    # required_room_type, which stays (column and data) but the engine stops
    # reading in a later Task -- rooms no longer have types.
    required_room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"))

    schedule_version: Mapped["ScheduleVersion"] = relationship()
    class_: Mapped["Class"] = relationship()
    subject: Mapped["Subject"] = relationship()
    required_teacher: Mapped["Teacher | None"] = relationship()
    required_room: Mapped["Room | None"] = relationship()
