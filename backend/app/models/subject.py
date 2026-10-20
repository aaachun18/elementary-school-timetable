from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.teacher import Teacher


class Subject(TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_subjects_school_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Task 98: the school this row belongs to. Every query a 教學組長 or
    # 一般老師 makes is limited to their own school (app/services/school_scope.py).
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)

    qualified_teachers: Mapped[list["Teacher"]] = relationship(
        secondary="teacher_subjects",
        back_populates="qualified_subjects",
        viewonly=True,
    )
