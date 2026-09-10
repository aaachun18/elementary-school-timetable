from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class Grade(TimestampMixin, Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(unique=True)

    classes: Mapped[list["Class"]] = relationship(back_populates="grade")


class Class(TimestampMixin, Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"))
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)

    grade: Mapped["Grade"] = relationship(back_populates="classes")
