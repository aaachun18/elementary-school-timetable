from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

# Grade.level values -- 國小 1-6, 國中 7-9, 高中 10-12 (shown as 一到三年級;
# see app/services/school_structure.py). A school's grades are built with
# the school and fixed by its type.
MIN_GRADE_LEVEL = 1
MAX_GRADE_LEVEL = 12


class Grade(TimestampMixin, Base):
    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("school_id", "level", name="uq_grades_school_level"),
        CheckConstraint(
            f"level BETWEEN {MIN_GRADE_LEVEL} AND {MAX_GRADE_LEVEL}",
            name="ck_grades_level_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Task 98: the school this row belongs to. Every query a 教學組長 or
    # 一般老師 makes is limited to their own school (app/services/school_scope.py).
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(100))
    level: Mapped[int] = mapped_column()

    classes: Mapped[list["Class"]] = relationship(back_populates="grade")


class Class(TimestampMixin, Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("grade_id", "name", name="uq_classes_grade_name"),
        CheckConstraint(
            "name_style IN ('NUMBER', 'HEAVENLY_STEM', 'VIRTUE')",
            name="ck_classes_name_style_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"))
    # One of the names class_name_options(grade level, name_style) offers
    # (app/services/school_structure.py), e.g. 一年甲班.
    name: Mapped[str] = mapped_column(String(100))
    # Which list the name was picked from: 一二三… / 甲乙丙… / 忠孝仁愛….
    name_style: Mapped[str] = mapped_column(
        String(20), default="NUMBER", server_default="NUMBER"
    )
    # 停用: left out of every new scheduling (開始排課, the record's
    # requirements, the home page), kept in old records. Not part of H12 --
    # a deactivated class never makes an existing timetable wrong.
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    grade: Mapped["Grade"] = relationship(back_populates="classes")
