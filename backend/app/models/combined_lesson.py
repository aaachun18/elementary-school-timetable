from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.class_subject_requirement import ClassSubjectRequirement
    from app.models.room import Room


class CombinedLesson(TimestampMixin, Base):
    """共同排課 (併班上課): some lessons of two or more class subject
    requirements of one 排課紀錄 (e.g. 一年甲班 and 二年甲班's 本土語文) are
    taught together -- each 合併節 is one lesson for all of them: same time
    slot, one room, taught by the members' required teachers together (or,
    if none names one, by one teacher the scheduler picks).

    Which lessons: every member has the same weekly periods and lesson
    pattern. Without a pattern, the first merged_count lessons (by
    sequence_number) of each member, one 合併節 each; with one, the blocks
    whose block_no is in block_nos (whole blocks only), one 合併節 per block.
    See services/combined_lesson.py for the rules and how the 合併節 line up.

    Room: room_id, a school room -- or None for the 原班教室 of
    homeroom_class_id (one of the members' classes; the class that started
    the merge by default). Members of a combined lesson count as one use of
    the room."""

    __tablename__ = "combined_lessons"
    __table_args__ = (
        CheckConstraint("merged_count >= 1", name="ck_combined_lessons_merged_count_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_version_id: Mapped[int] = mapped_column(ForeignKey("schedule_versions.id"))
    merged_count: Mapped[int] = mapped_column()
    # Comma separated block numbers ("1,3") when the members have a lesson
    # pattern; None without one.
    block_nos: Mapped[str | None] = mapped_column(String(50))
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"))
    homeroom_class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"))

    room: Mapped["Room | None"] = relationship()
    members: Mapped[list["CombinedLessonMember"]] = relationship(
        back_populates="combined_lesson", order_by="CombinedLessonMember.position"
    )


class CombinedLessonMember(TimestampMixin, Base):
    """One requirement of a combined lesson. A requirement is in at most one
    combined lesson. position 0 is the class that started the merge."""

    __tablename__ = "combined_lesson_members"
    __table_args__ = (
        UniqueConstraint(
            "class_subject_requirement_id", name="uq_combined_lesson_member_requirement"
        ),
        UniqueConstraint(
            "combined_lesson_id", "position", name="uq_combined_lesson_member_position"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    combined_lesson_id: Mapped[int] = mapped_column(ForeignKey("combined_lessons.id"))
    class_subject_requirement_id: Mapped[int] = mapped_column(
        ForeignKey("class_subject_requirements.id")
    )
    position: Mapped[int] = mapped_column()

    combined_lesson: Mapped["CombinedLesson"] = relationship(back_populates="members")
    class_subject_requirement: Mapped["ClassSubjectRequirement"] = relationship()
