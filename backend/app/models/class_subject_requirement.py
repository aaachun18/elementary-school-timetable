from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.academic_year import Semester
    from app.models.grade_class import Class
    from app.models.subject import Subject
    from app.models.teacher import Teacher


class ClassSubjectRequirement(TimestampMixin, Base):
    """How many weekly periods a class needs of a subject in a semester
    (and optional constraints on who/where), independent of whether any
    Lesson has actually been scheduled for it yet."""

    __tablename__ = "class_subject_requirements"
    __table_args__ = (
        UniqueConstraint(
            "semester_id",
            "class_id",
            "subject_id",
            name="uq_class_subject_requirement",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    weekly_periods: Mapped[int] = mapped_column()
    required_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.id")
    )
    required_room_type: Mapped[str | None] = mapped_column(String(100))
    consecutive_limit: Mapped[int | None] = mapped_column()

    semester: Mapped["Semester"] = relationship()
    class_: Mapped["Class"] = relationship()
    subject: Mapped["Subject"] = relationship()
    required_teacher: Mapped["Teacher | None"] = relationship()
