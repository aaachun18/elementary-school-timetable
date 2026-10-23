"""共同排課 (併班上課): lessons of several class subject requirements of one
排課紀錄 taught together. Set in the wizard's 共同排課 step, only while the
record is 尚未排課 (SettingsLockedError otherwise).

Rules for a combined lesson (CombinedLessonRuleError -> 422 otherwise):
- two or more requirements of the record, of different classes, none of
  them already in another combined lesson;
- the same weekly periods and the same lesson pattern;
- without a pattern: merged_count (1 .. weekly periods) of their lessons
  are merged -- the first ones by sequence_number, one 合併節 each;
- with a pattern: whole blocks only -- block_nos (some of 1 .. the number
  of blocks), one 合併節 per block; merged_count is their total;
- the room: a school room (active), or the 原班教室 of one member's class;
- fixed time slots: within a 合併節, every member's fixed lesson must be
  fixed to the same slot; one member's fixed slot then fixes all of them
  (it is copied to the others), and so does changing one later
  (services/lesson.py).

The 合併節 line up member by member: lesson i of member A goes with lesson
i of member B. Teachers come from the members' required teachers (the
scheduler, services/scheduler.py), so nothing about teachers is stored here.
"""

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.combined_lesson import CombinedLesson, CombinedLessonMember
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule_version import ScheduleVersion
from app.schemas.combined_lesson import (
    CombinedInstanceRead,
    CombinedLessonCreate,
    CombinedLessonFields,
    CombinedLessonRead,
)
from app.services.exceptions import (
    CombinedLessonRuleError,
    InactiveRoomAssignmentError,
    raise_for_integrity_error,
)
from app.services.lesson_pattern import parse_lesson_pattern
# A module import, not names: schedule_version -> version_contents -> this
# module is a cycle, and the names are only needed at call time.
from app.services import schedule_version as schedule_version_service
from app.services.school_scope import ensure_references_in_school, get_in_school

NOT_IN_RECORD_MESSAGE = "合併的課必須都是這筆排課紀錄的科目需求"
SAME_CLASS_MESSAGE = "同一個班級不能和自己合併"
ALREADY_COMBINED_MESSAGE = "其中有科目需求已經設定了其他共同排課"
PERIODS_DIFFER_MESSAGE = "只有每週節數相同的課才能合併"
PATTERN_DIFFER_MESSAGE = "合併的課連堂樣式必須相同"
MERGED_COUNT_MESSAGE = "合併節數必須介於 1 到每週節數之間"
BLOCK_NOS_MESSAGE = "有連堂的課只能以整組連堂合併，請選擇要合併哪幾組"
HOMEROOM_CLASS_MESSAGE = "上課教室必須是合併班級之一的原班教室，或學校的教室"
FIXED_SLOTS_DIFFER_MESSAGE = "合併的各班這一節固定在不同的時段，請先調整固定時段再合併"


@dataclass(frozen=True)
class CombinedInstance:
    """One 合併節: key "<combined lesson id>:<n>", and per member its
    lessons of it in period order."""

    key: str
    member_lesson_ids: tuple[tuple[int, ...], ...]


def _members(db: Session, combined: CombinedLesson) -> list[ClassSubjectRequirement]:
    return [
        requirement
        for requirement in db.scalars(
            select(ClassSubjectRequirement)
            .join(
                CombinedLessonMember,
                CombinedLessonMember.class_subject_requirement_id == ClassSubjectRequirement.id,
            )
            .where(CombinedLessonMember.combined_lesson_id == combined.id)
            .order_by(CombinedLessonMember.position)
        ).all()
    ]


def _block_nos(combined: CombinedLesson) -> list[int] | None:
    if combined.block_nos is None:
        return None
    return [int(part) for part in combined.block_nos.split(",") if part != ""]


def _lessons_of(db: Session, requirement_id: int) -> list[Lesson]:
    return list(
        db.scalars(
            select(Lesson)
            .where(Lesson.class_subject_requirement_id == requirement_id)
            .order_by(Lesson.sequence_number)
        ).all()
    )


def instances_of(db: Session, combined: CombinedLesson) -> list[CombinedInstance]:
    """The combined lesson's 合併節, from the lessons as they are now. A
    合併節 a member has no lessons for yet is left out (lessons are made by
    generate-lessons)."""
    members_lessons = [_lessons_of(db, requirement.id) for requirement in _members(db, combined)]
    block_nos = _block_nos(combined)
    groups: list[list[tuple[int, ...]]] = []
    if block_nos is None:
        for index in range(combined.merged_count):
            groups.append(
                [
                    (lessons[index].id,) if index < len(lessons) else ()
                    for lessons in members_lessons
                ]
            )
    else:
        for block_no in block_nos:
            groups.append(
                [
                    tuple(
                        lesson.id
                        for lesson in sorted(
                            (item for item in lessons if item.block_no == block_no),
                            key=lambda item: item.block_seq or 0,
                        )
                    )
                    for lessons in members_lessons
                ]
            )
    instances: list[CombinedInstance] = []
    for number, member_lesson_ids in enumerate(groups, start=1):
        sizes = {len(lesson_ids) for lesson_ids in member_lesson_ids}
        if len(sizes) != 1 or 0 in sizes:
            continue
        instances.append(CombinedInstance(f"{combined.id}:{number}", tuple(member_lesson_ids)))
    return instances


def combined_lessons_of_version(db: Session, version_id: int) -> list[CombinedLesson]:
    return list(
        db.scalars(
            select(CombinedLesson)
            .where(CombinedLesson.schedule_version_id == version_id)
            .order_by(CombinedLesson.id)
        ).all()
    )


def partner_lessons(db: Session, version_id: int) -> dict[int, list[int]]:
    """lesson_id -> the other members' lessons that sit in the same slot
    with it (lessons in no combined lesson are absent)."""
    partners: dict[int, list[int]] = {}
    for combined in combined_lessons_of_version(db, version_id):
        for instance in instances_of(db, combined):
            for index in range(len(instance.member_lesson_ids[0])):
                same_slot = [lesson_ids[index] for lesson_ids in instance.member_lesson_ids]
                for lesson_id in same_slot:
                    partners[lesson_id] = [other for other in same_slot if other != lesson_id]
    return partners


# --- read ---


def to_read(db: Session, combined: CombinedLesson) -> CombinedLessonRead:
    return CombinedLessonRead(
        id=combined.id,
        schedule_version_id=combined.schedule_version_id,
        requirement_ids=[requirement.id for requirement in _members(db, combined)],
        merged_count=combined.merged_count,
        block_nos=_block_nos(combined),
        room_id=combined.room_id,
        homeroom_class_id=combined.homeroom_class_id,
        instances=[
            CombinedInstanceRead(
                key=instance.key,
                member_lesson_ids=[list(lesson_ids) for lesson_ids in instance.member_lesson_ids],
            )
            for instance in instances_of(db, combined)
        ],
        created_at=combined.created_at,
        updated_at=combined.updated_at,
    )


def get_combined_lessons(
    db: Session, version_id: int, *, school_id: int, role: str | None = None
) -> list[CombinedLessonRead] | None:
    """None if the record doesn't exist in the school (or, for a TEACHER,
    isn't published)."""
    if schedule_version_service.get_schedule_version(db, version_id, school_id=school_id, role=role) is None:
        return None
    return [to_read(db, combined) for combined in combined_lessons_of_version(db, version_id)]


# --- write ---


def _validated(
    db: Session,
    schedule_version: ScheduleVersion,
    data: CombinedLessonFields,
    *,
    school_id: int,
    combined_id: int | None,
) -> tuple[list[ClassSubjectRequirement], int, str | None, int | None]:
    """Checks the rules (module docstring). Returns the members (in
    order), merged_count, block_nos as stored, and homeroom_class_id."""
    ensure_references_in_school(db, school_id, [(Room, data.room_id)])
    requirements: list[ClassSubjectRequirement] = []
    for requirement_id in data.requirement_ids:
        requirement = db.get(ClassSubjectRequirement, requirement_id)
        if requirement is None or requirement.schedule_version_id != schedule_version.id:
            raise CombinedLessonRuleError(NOT_IN_RECORD_MESSAGE)
        requirements.append(requirement)
    if len({requirement.id for requirement in requirements}) != len(requirements) or len(
        {requirement.class_id for requirement in requirements}
    ) != len(requirements):
        raise CombinedLessonRuleError(SAME_CLASS_MESSAGE)
    taken = db.scalar(
        select(CombinedLessonMember.id).where(
            CombinedLessonMember.class_subject_requirement_id.in_(data.requirement_ids),
            CombinedLessonMember.combined_lesson_id != (combined_id or 0),
        )
    )
    if taken is not None:
        raise CombinedLessonRuleError(ALREADY_COMBINED_MESSAGE)
    first = requirements[0]
    if any(requirement.weekly_periods != first.weekly_periods for requirement in requirements):
        raise CombinedLessonRuleError(PERIODS_DIFFER_MESSAGE)
    if any(requirement.lesson_pattern != first.lesson_pattern for requirement in requirements):
        raise CombinedLessonRuleError(PATTERN_DIFFER_MESSAGE)

    if first.lesson_pattern is None:
        merged_count = data.merged_count
        if merged_count is None or not 1 <= merged_count <= first.weekly_periods or data.block_nos:
            raise CombinedLessonRuleError(MERGED_COUNT_MESSAGE)
        block_nos = None
    else:
        sizes = parse_lesson_pattern(first.lesson_pattern)
        chosen = sorted(set(data.block_nos or []))
        if not chosen or any(not 1 <= block_no <= len(sizes) for block_no in chosen):
            raise CombinedLessonRuleError(BLOCK_NOS_MESSAGE)
        merged_count = sum(sizes[block_no - 1] for block_no in chosen)
        block_nos = ",".join(str(block_no) for block_no in chosen)

    homeroom_class_id: int | None = None
    if data.room_id is None:
        homeroom_class_id = data.homeroom_class_id or first.class_id
        if homeroom_class_id not in {requirement.class_id for requirement in requirements}:
            raise CombinedLessonRuleError(HOMEROOM_CLASS_MESSAGE)
    else:
        room = db.get(Room, data.room_id)
        assert room is not None  # checked above
        if not room.is_active:
            raise InactiveRoomAssignmentError(f"Room {room.id} is inactive.")
    return requirements, merged_count, block_nos, homeroom_class_id


def _stage_align_fixed_slots(db: Session, combined: CombinedLesson) -> None:
    """Within each 合併節, the members' fixed slots must agree; one fixed
    member fixes the others (staged)."""
    for instance in instances_of(db, combined):
        for index in range(len(instance.member_lesson_ids[0])):
            lessons = [db.get(Lesson, lesson_ids[index]) for lesson_ids in instance.member_lesson_ids]
            fixed = {lesson.fixed_time_slot_id for lesson in lessons if lesson and lesson.fixed_time_slot_id}
            if len(fixed) > 1:
                raise CombinedLessonRuleError(FIXED_SLOTS_DIFFER_MESSAGE)
            if fixed:
                slot_id = next(iter(fixed))
                for lesson in lessons:
                    if lesson is not None:
                        lesson.fixed_time_slot_id = slot_id


def _save(
    db: Session,
    schedule_version: ScheduleVersion,
    combined: CombinedLesson | None,
    data: CombinedLessonFields,
    *,
    school_id: int,
) -> CombinedLesson:
    schedule_version_service.lock_record_for_settings(db, schedule_version)
    requirements, merged_count, block_nos, homeroom_class_id = _validated(
        db, schedule_version, data, school_id=school_id, combined_id=None if combined is None else combined.id
    )
    # The lessons have to exist to line them up (and to carry fixed slots).
    schedule_version_service.generate_lessons(db, schedule_version.id)
    schedule_version_service.lock_record_for_settings(db, schedule_version)
    try:
        if combined is None:
            combined = CombinedLesson(schedule_version_id=schedule_version.id, merged_count=merged_count)
            db.add(combined)
        else:
            db.execute(
                delete(CombinedLessonMember).where(
                    CombinedLessonMember.combined_lesson_id == combined.id
                )
            )
        combined.merged_count = merged_count
        combined.block_nos = block_nos
        combined.room_id = data.room_id
        combined.homeroom_class_id = homeroom_class_id
        db.flush()
        db.add_all(
            CombinedLessonMember(
                combined_lesson_id=combined.id,
                class_subject_requirement_id=requirement.id,
                position=position,
            )
            for position, requirement in enumerate(requirements)
        )
        db.flush()
        _stage_align_fixed_slots(db, combined)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    except CombinedLessonRuleError:
        db.rollback()
        raise
    db.refresh(combined)
    return combined


def create_combined_lesson(
    db: Session, data: CombinedLessonCreate, *, school_id: int
) -> CombinedLessonRead | None:
    """None if the record doesn't exist in the school."""
    schedule_version = get_in_school(db, ScheduleVersion, data.schedule_version_id, school_id)
    if schedule_version is None:
        return None
    return to_read(db, _save(db, schedule_version, None, data, school_id=school_id))


def _get_with_version(
    db: Session, combined_id: int, school_id: int
) -> tuple[CombinedLesson, ScheduleVersion] | None:
    combined = db.get(CombinedLesson, combined_id)
    if combined is None:
        return None
    schedule_version = get_in_school(db, ScheduleVersion, combined.schedule_version_id, school_id)
    if schedule_version is None:
        return None
    return combined, schedule_version


def update_combined_lesson(
    db: Session, combined_id: int, data: CombinedLessonFields, *, school_id: int
) -> CombinedLessonRead | None:
    found = _get_with_version(db, combined_id, school_id)
    if found is None:
        return None
    combined, schedule_version = found
    return to_read(db, _save(db, schedule_version, combined, data, school_id=school_id))


def delete_combined_lesson(db: Session, combined_id: int, *, school_id: int) -> bool:
    found = _get_with_version(db, combined_id, school_id)
    if found is None:
        return False
    combined, schedule_version = found
    schedule_version_service.lock_record_for_settings(db, schedule_version)
    stage_delete(db, [combined.id])
    db.commit()
    return True


# --- for the other services (staged, never committed) ---


def stage_delete(db: Session, combined_ids: list[int]) -> None:
    if not combined_ids:
        return
    db.execute(
        delete(CombinedLessonMember).where(CombinedLessonMember.combined_lesson_id.in_(combined_ids))
    )
    db.execute(delete(CombinedLesson).where(CombinedLesson.id.in_(combined_ids)))
    db.flush()


def stage_delete_for_requirements(db: Session, requirement_ids: list[int]) -> int:
    """The combined lessons any of these requirements is in -- they no
    longer hold together once a member changes or goes. Returns how many."""
    if not requirement_ids:
        return 0
    combined_ids = sorted(
        set(
            db.scalars(
                select(CombinedLessonMember.combined_lesson_id).where(
                    CombinedLessonMember.class_subject_requirement_id.in_(requirement_ids)
                )
            ).all()
        )
    )
    stage_delete(db, combined_ids)
    return len(combined_ids)


def is_combined(db: Session, requirement_id: int) -> bool:
    return (
        db.scalar(
            select(CombinedLessonMember.id).where(
                CombinedLessonMember.class_subject_requirement_id == requirement_id
            )
        )
        is not None
    )


def stage_delete_for_version(db: Session, version_id: int) -> None:
    stage_delete(
        db,
        [combined.id for combined in combined_lessons_of_version(db, version_id)],
    )


def stage_copy(
    db: Session, source_id: int, target_id: int, requirement_id_map: dict[int, int]
) -> None:
    """Copies of the source record's combined lessons, onto the copied
    requirements."""
    for source in combined_lessons_of_version(db, source_id):
        copied = CombinedLesson(
            schedule_version_id=target_id,
            merged_count=source.merged_count,
            block_nos=source.block_nos,
            room_id=source.room_id,
            homeroom_class_id=source.homeroom_class_id,
        )
        db.add(copied)
        db.flush()
        db.add_all(
            CombinedLessonMember(
                combined_lesson_id=copied.id,
                class_subject_requirement_id=requirement_id_map[member.class_subject_requirement_id],
                position=member.position,
            )
            for member in source.members
        )
    db.flush()
