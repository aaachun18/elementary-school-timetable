from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.room import Room


# Task 98: Grade.level values -- 國小 1-6, 國中 7-9 (the request-side
# rule is app/services/grade_levels.py).
MIN_GRADE_LEVEL = 1
MAX_GRADE_LEVEL = 9


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

    id: Mapped[int] = mapped_column(primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"))
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)
    homeroom_room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"))

    grade: Mapped["Grade"] = relationship(back_populates="classes")
    homeroom_room: Mapped["Room | None"] = relationship()
