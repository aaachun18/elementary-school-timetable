"""Pure, framework-independent data structures for the Constraint Engine.

No SQLAlchemy, no FastAPI, no database access anywhere in this module (or
anywhere under scheduling_engine/) -- see AGENTS.md section 4. Converting
ORM rows into these dataclasses is the API layer's job (a later Task), not
the engine's.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LessonAssignment:
    """One lesson's placement on the timetable -- the flattened,
    engine-friendly equivalent of a `Schedule` row.

    Flattened rather than referencing related objects (no Lesson/Teacher/
    Room objects here) so constraints can compare plain values without
    needing to know how those relationships are structured, and so a whole
    candidate schedule can be represented as a simple `list[LessonAssignment]`
    that's trivial to copy/mutate during search (Greedy/Backtracking, a
    later Task).

    class_subject_requirement_id/class_id/subject_id come from the Lesson's
    ClassSubjectRequirement (not columns on Schedule itself), but
    constraints need them directly -- H2 checks class_id, H5 checks
    subject_id, H6/H9 (Task 18) look up rules keyed by
    class_subject_requirement_id -- without walking relationships, so
    they're included here rather than left for a join.

    teacher_id/time_slot_id/room_id are Optional because a Schedule row can
    exist before every part of the assignment is filled in (see
    app/models/schedule.py). A constraint only checks assignments where the
    columns it cares about are actually set -- an unplaced lesson can't
    conflict with anything.
    """

    lesson_id: int
    class_subject_requirement_id: int
    class_id: int
    subject_id: int
    teacher_id: int | None
    time_slot_id: int | None
    room_id: int | None


@dataclass(frozen=True)
class TeacherUnavailability:
    """One (teacher_id, time_slot_id) pair the teacher is NOT available
    for. Mirrors the DB's TeacherAvailability table one row at a time:
    existence = unavailable, no row = available (the "精簡設計" decision
    from Task 4 -- there is no is_available column to read instead)."""

    teacher_id: int
    time_slot_id: int


@dataclass(frozen=True)
class TeacherQualification:
    """One (teacher_id, subject_id) pair the teacher IS qualified to
    teach. Mirrors the DB's TeacherSubject table one row at a time."""

    teacher_id: int
    subject_id: int


@dataclass(frozen=True)
class RequiredTeacherRule:
    """H6: this requirement's lessons must be taught by exactly this
    teacher. Sparse list, same pattern as TeacherUnavailability -- a
    requirement with no required teacher simply has no entry here at all
    (ClassSubjectRequirement.required_teacher_id is nullable in the DB;
    only the non-null rows become a rule)."""

    class_subject_requirement_id: int
    required_teacher_id: int


@dataclass(frozen=True)
class RoomTypeRequirement:
    """H9 (half 1): this requirement's lessons must be held in a room of
    this type. Sparse list for the same reason as RequiredTeacherRule --
    no entry means "no room-type restriction" (原班上課)."""

    class_subject_requirement_id: int
    required_room_type: str


@dataclass(frozen=True)
class RoomInfo:
    """H9 (half 2): what type of room an actual Room is -- the other side
    of the comparison RoomTypeConstraint makes. Mirrors Room.room_type."""

    room_id: int
    room_type: str


@dataclass(frozen=True)
class TimeSlotInfo:
    """H11: whether a time slot is actually a teaching period (as opposed
    to e.g. recess/lunch). Mirrors TimeSlot.is_teaching_period."""

    time_slot_id: int
    is_teaching_period: bool


@dataclass(frozen=True)
class ActiveStatusInfo:
    """H12: whether one teacher/class/subject/room is currently active.

    One shared dataclass (entity_type + entity_id) rather than four
    near-identical TeacherActiveStatus/ClassActiveStatus/SubjectActiveStatus/
    RoomActiveStatus classes: the shape -- an id plus a boolean -- is
    identical across all four, and the only thing that varies is which
    id-space it's drawn from. A one-field discriminated union beats four
    structurally-duplicate dataclasses that would all need the exact same
    constraint-side handling anyway.

    Unlike TeacherUnavailability/RequiredTeacherRule/RoomTypeRequirement
    (genuine sparse/exception lists -- existence itself carries meaning),
    is_active is a plain boolean column that already exists directly on
    each entity's own table, so this carries the real True/False value
    rather than only listing the inactive ones -- same reasoning as
    TimeSlotInfo carrying `is_teaching_period` directly instead of a
    "non-teaching slots" list.
    """

    entity_type: Literal["teacher", "class", "subject", "room"]
    entity_id: int
    is_active: bool
