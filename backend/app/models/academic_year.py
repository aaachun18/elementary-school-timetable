from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class AcademicYear(TimestampMixin, Base):
    __tablename__ = "academic_years"
    __table_args__ = (
        UniqueConstraint("school_id", "year", name="uq_academic_years_school_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Task 98: the school this row belongs to. Every query a 教學組長 or
    # 一般老師 makes is limited to their own school (app/services/school_scope.py).
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    year: Mapped[int] = mapped_column()
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
