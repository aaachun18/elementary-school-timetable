from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.grade_class import Grade
    from app.models.subject import Subject

# Same range the wizard offers for a requirement's weekly periods.
MIN_GRADE_WEEKLY_PERIODS = 1
MAX_GRADE_WEEKLY_PERIODS = 6


class GradeSubjectRequirement(TimestampMixin, Base):
    """The school's standing rule: every class of this grade needs this
    many periods of this subject a week (學校資料 > 科目需求). The wizard
    copies it into each semester's ClassSubjectRequirement rows
    (services/class_subject_requirement.py sync_semester_requirements());
    those then only add the lesson pattern, teacher and room."""

    __tablename__ = "grade_subject_requirements"
    __table_args__ = (
        UniqueConstraint("grade_id", "subject_id", name="uq_grade_subject_requirement"),
        CheckConstraint(
            f"weekly_periods BETWEEN {MIN_GRADE_WEEKLY_PERIODS} AND {MAX_GRADE_WEEKLY_PERIODS}",
            name="ck_grade_subject_requirements_weekly_periods_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    weekly_periods: Mapped[int] = mapped_column()

    grade: Mapped["Grade"] = relationship()
    subject: Mapped["Subject"] = relationship()
