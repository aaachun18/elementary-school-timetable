from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class AcademicYear(TimestampMixin, Base):
    __tablename__ = "academic_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    semesters: Mapped[list["Semester"]] = relationship(
        back_populates="academic_year"
    )


class Semester(TimestampMixin, Base):
    __tablename__ = "semesters"
    __table_args__ = (
        CheckConstraint("number IN (1, 2)", name="ck_semesters_number_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"))
    number: Mapped[int] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    academic_year: Mapped["AcademicYear"] = relationship(back_populates="semesters")
