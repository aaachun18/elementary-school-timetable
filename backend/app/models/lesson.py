from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.class_subject_requirement import ClassSubjectRequirement
    from app.models.time_slot import TimeSlot


class Lesson(TimestampMixin, Base):
    """One required lesson instance for a ClassSubjectRequirement -- e.g. if
    a requirement needs 3 weekly_periods, there are 3 Lesson rows (sequence
    1..3). Version-independent: this is the requirement checklist, not a
    scheduled result. See Schedule for where a Lesson actually lands on the
    timetable within a specific ScheduleVersion."""

    __tablename__ = "lessons"
    __table_args__ = (
        # Task 87: a lesson is either in a block (both set) or not (both
        # NULL) -- never half of it.
        CheckConstraint(
            "(block_no IS NULL) = (block_seq IS NULL)",
            name="ck_lessons_block_fields_together",
        ),
        UniqueConstraint(
            "class_subject_requirement_id",
            "sequence_number",
            name="uq_lesson_requirement_sequence",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_subject_requirement_id: Mapped[int] = mapped_column(
        ForeignKey("class_subject_requirements.id")
    )
    # Purely a technical index distinguishing lesson instances of the same
    # requirement (e.g. "the 2nd of 3 weekly Math lessons") -- no other
    # meaning.
    sequence_number: Mapped[int] = mapped_column()
    # Task 28: pins THIS specific lesson instance to a time slot before
    # scheduling even runs -- e.g. one of a requirement's 2 weekly lessons
    # needs to always land on Wednesday period 3, while the other stays
    # free for the algorithm to place. Deliberately placed on Lesson, not
    # ClassSubjectRequirement, since "some but not all lessons of this
    # requirement are fixed" cannot be expressed at the requirement level.
    fixed_time_slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("time_slots.id")
    )
    # Task 87: which block of the requirement's lesson_pattern this lesson
    # belongs to (1 = the first / longest block) and its place in it (1 =
    # first period). Both None when the requirement has no pattern. Set by
    # generate-lessons and kept in step when the pattern changes.
    block_no: Mapped[int | None] = mapped_column()
    block_seq: Mapped[int | None] = mapped_column()

    class_subject_requirement: Mapped["ClassSubjectRequirement"] = relationship()
    fixed_time_slot: Mapped["TimeSlot | None"] = relationship()
