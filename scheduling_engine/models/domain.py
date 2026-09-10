"""Pure, framework-independent data structures for the Constraint Engine.

No SQLAlchemy, no FastAPI, no database access anywhere in this module (or
anywhere under scheduling_engine/) -- see AGENTS.md section 4. Converting
ORM rows into these dataclasses is the API layer's job (a later Task), not
the engine's.
"""

from dataclasses import dataclass


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

    class_id/subject_id come from the Lesson's ClassSubjectRequirement (not
    columns on Schedule itself), but constraints need them directly -- H2
    checks class_id, H5 checks subject_id -- without walking relationships,
    so they're included here rather than left for a join.

    teacher_id/time_slot_id/room_id are Optional because a Schedule row can
    exist before every part of the assignment is filled in (see
    app/models/schedule.py). A constraint only checks assignments where the
    columns it cares about are actually set -- an unplaced lesson can't
    conflict with anything.
    """

    lesson_id: int
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
