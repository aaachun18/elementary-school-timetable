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
    constraints need them directly -- H2 and H13 check class_id, H6/H9
    (Task 18) look up rules keyed by class_subject_requirement_id --
    without walking relationships, so they're included here rather than
    left for a join.

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
    for. Task 98: mirrors the DB's SemesterTeacherUnavailability table (the
    semester being scheduled) one row at a time: existence = unavailable,
    no row = available."""

    teacher_id: int
    time_slot_id: int


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
class RequiredRoomRule:
    """H9 Required Room (Task 98, replaces the room-type rule): this
    requirement's lessons must be held in exactly this room -- the special
    room ClassSubjectRequirement.required_room_id names. Sparse: no entry
    means no special room (原班上課)."""

    class_subject_requirement_id: int
    room_id: int


@dataclass(frozen=True)
class DefaultRoom:
    """Task 92B: this requirement's lessons are held in this room -- the
    class's homeroom (原班上課). Not searched: it is the only room candidate
    (candidate_room_ids()), so a whole lesson block and a fixed lesson get
    it too. Task 98: a RequiredRoomRule for the same requirement wins over
    it. Sparse: no entry (and no required room) means "no room" (room_id
    None)."""

    class_subject_requirement_id: int
    room_id: int


@dataclass(frozen=True)
class ClassAllowedTimeSlots:
    """H13 Grade Time Slots (Task 98): the only time slots this class may
    be scheduled in -- the slots its grade is open for in the semester
    (SemesterGradeTimeSlot). Sparse: a class with no entry is not
    restricted at all."""

    class_id: int
    time_slot_ids: frozenset[int]


@dataclass(frozen=True)
class TimeSlotInfo:
    """H11: whether a time slot is actually a teaching period (as opposed
    to e.g. recess/lunch). Mirrors TimeSlot.is_teaching_period."""

    time_slot_id: int
    is_teaching_period: bool


@dataclass(frozen=True)
class TimeSlotPosition:
    """Task 87: where a time slot sits in the week -- what "consecutive
    periods on one day" means for lesson blocks. Mirrors TimeSlot.weekday /
    TimeSlot.period."""

    time_slot_id: int
    weekday: int
    period: int


@dataclass(frozen=True)
class LessonBlock:
    """Task 87: lessons of one requirement that must be taught as one block
    (a lesson_pattern block, e.g. the "2" of "2+1"): same day, adjacent
    teaching periods in lesson_ids order, one teacher, one room. Different
    blocks of the same requirement go on different days. A lesson in no
    block is scheduled on its own, exactly as before."""

    class_subject_requirement_id: int
    block_no: int
    # In block order (block_seq 1, 2, ...): lesson_ids[0] takes the first
    # period of the block.
    lesson_ids: tuple[int, ...]


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

    Unlike TeacherUnavailability/RequiredTeacherRule/RequiredRoomRule
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


@dataclass(frozen=True)
class RequirementPeriods:
    """H7: how many weekly periods (= how many Lesson rows) a requirement
    needs in total. Unlike the sparse rule lists above (RequiredTeacherRule
    etc.), there is no "no restriction" case here -- every requirement
    being scheduled has an exact target, so this should have one entry per
    requirement, not just the exceptional ones."""

    class_subject_requirement_id: int
    weekly_periods: int


@dataclass(frozen=True)
class TeacherWorkloadLimit:
    """H8: the maximum weekly periods one teacher may be scheduled for.
    Task 98: mirrors SemesterTeacher.max_weekly_periods."""

    teacher_id: int
    max_weekly_periods: int


@dataclass(frozen=True)
class HomeroomTeacher:
    """導師: this teacher is the homeroom teacher of this class in the
    record being scheduled (SemesterTeacher.homeroom_class_id). Sparse: a
    teacher with no entry is no class's 導師.

    The search keeps a 導師 off other classes' lessons that name no
    required teacher whenever a timetable allows it, and otherwise gives
    them as few such periods as it can (algorithms/homeroom.py)."""

    teacher_id: int
    class_id: int


@dataclass(frozen=True)
class TeacherMinimumWorkload:
    """Task 88: the minimum weekly periods one teacher should teach. Task
    98: mirrors SemesterTeacher.min_weekly_periods; None means no minimum. Only the schedule
    check reads it (as a WARNING) -- it never limits the search."""

    teacher_id: int
    min_weekly_periods: int | None


@dataclass(frozen=True)
class CombinedLesson:
    """共同排課: one 合併節 -- the lessons of several classes taught together.
    member_lesson_ids has one tuple per member requirement (the class that
    started the merge first), each the member's lessons of this 合併節 in
    period order: one lesson, or a whole block (連堂). Lesson i of every
    member goes to the same time slot, all of them in room_id (None = a
    class's own room, not a school room).

    teacher_ids: the members' required teachers, in member order without
    repeats -- they teach the 合併節 together (each member's lessons keep
    their own required teacher; a member without one gets the first of
    them). Empty: the scheduler picks one teacher for every member.

    Whoever shares a 合併節 is not in conflict with each other: one teacher
    on two members' lessons at that slot is one lesson, and the room is used
    once (constraints read joint_keys())."""

    key: str
    member_lesson_ids: tuple[tuple[int, ...], ...]
    room_id: int | None
    teacher_ids: tuple[int, ...]


def joint_keys(combined_lessons: "list[CombinedLesson]") -> dict[int, str]:
    """lesson_id -> the key it shares with the other members' lessons that
    must sit in the same time slot ("<合併節 key>:<position>"). A lesson in
    no combined lesson is absent."""
    keys: dict[int, str] = {}
    for combined in combined_lessons:
        for lesson_ids in combined.member_lesson_ids:
            for index, lesson_id in enumerate(lesson_ids):
                keys[lesson_id] = f"{combined.key}:{index}"
    return keys


def occupancy_key(assignment: LessonAssignment, keys: dict[int, str]) -> str:
    """What one lesson occupies: its 合併節 position, shared with the other
    members' lessons there, or the lesson itself."""
    return keys.get(assignment.lesson_id, f"lesson:{assignment.lesson_id}")


@dataclass(frozen=True)
class RoomCapacity:
    """H3: how many classes may use the room at the same time (a combined
    lesson counts once). Sparse: a room with no entry holds one."""

    room_id: int
    max_classes: int
