"""導師 rule: a class's homeroom teacher (導師) does not teach other classes'
lessons that name no required teacher -- whenever a timetable that keeps
every hard constraint allows it. When none does, the timetable gives 導師
as few such periods as possible.

A "cross-homeroom period" is one placed lesson whose teacher is the 導師 of
a DIFFERENT class, and whose requirement names no required teacher (H6) --
a required teacher is the school's own choice and never counts. A lesson
of a 合併節 whose teachers are named by its members counts as named too.
Teaching their own class, or any class when they are no 導師, costs
nothing.

How the search uses it (forward_checking.py):
1. First the rule is a hard constraint: every candidate with a
   cross-homeroom period is removed (budget 0).
2. If that finds no timetable, the rule is relaxed: the search prefers
   candidates without such periods. The timetable found is improved by
   reduce_cross_homeroom() below (handing a requirement to another
   teacher, same time slots), then the search runs again allowing at most
   one period fewer than the best so far, until that fails or time runs
   out. The best (fewest periods) complete, legal timetable wins.

Pure: no database, no FastAPI (AGENTS.md section 4).
"""

from collections import defaultdict
from dataclasses import dataclass, replace

from scheduling_engine.algorithms.resources import SchedulingResources
from scheduling_engine.constraints.base import BaseConstraint
from scheduling_engine.models.domain import LessonAssignment


@dataclass(frozen=True)
class HomeroomRule:
    """What decides whether one placed lesson is a cross-homeroom period."""

    # teacher -> the class they are 導師 of.
    homeroom_class_by_teacher: dict[int, int]
    # Requirements with a required teacher (H6): never counted.
    named_requirement_ids: frozenset[int]
    # Lessons of a 合併節 whose teachers are named: never counted.
    named_lesson_ids: frozenset[int]

    @property
    def active(self) -> bool:
        return bool(self.homeroom_class_by_teacher)

    def is_cross_teacher(self, teacher_id: int, class_id: int) -> bool:
        """True: this teacher is the 導師 of a class other than `class_id`."""
        homeroom_class = self.homeroom_class_by_teacher.get(teacher_id)
        return homeroom_class is not None and homeroom_class != class_id

    def is_cross(self, assignment: LessonAssignment) -> bool:
        if assignment.teacher_id is None:
            return False
        if assignment.class_subject_requirement_id in self.named_requirement_ids:
            return False
        if assignment.lesson_id in self.named_lesson_ids:
            return False
        return self.is_cross_teacher(assignment.teacher_id, assignment.class_id)

    def count(self, assignments: list[LessonAssignment] | tuple[LessonAssignment, ...]) -> int:
        """How many cross-homeroom periods `assignments` hold."""
        return sum(1 for assignment in assignments if self.is_cross(assignment))


def build_homeroom_rule(resources: SchedulingResources) -> HomeroomRule:
    return HomeroomRule(
        homeroom_class_by_teacher={item.teacher_id: item.class_id for item in resources.homeroom_teachers},
        named_requirement_ids=frozenset(
            rule.class_subject_requirement_id for rule in resources.required_teacher_rules
        ),
        named_lesson_ids=frozenset(
            lesson_id
            for combined in resources.combined_lessons
            if combined.teacher_ids
            for lesson_ids in combined.member_lesson_ids
            for lesson_id in lesson_ids
        ),
    )


def reduce_cross_homeroom(
    assignments: list[LessonAssignment],
    resources: SchedulingResources,
    rule: HomeroomRule,
    constraints: list[BaseConstraint],
) -> list[LessonAssignment]:
    """Hands each requirement taught by another class's 導師 to a teacher
    who costs nothing there (not a 導師, or this class's own 導師), keeping
    every lesson in its time slot and room. A change is kept only when the
    whole timetable still passes every constraint in `constraints` -- so
    the result is as legal as the input, with at most as many
    cross-homeroom periods. Requirements with a lesson in a 合併節 are left
    alone (its teacher is shared with the other classes). Deterministic:
    requirements and teachers are tried in id / resources order."""
    combined_lesson_ids = {
        lesson_id
        for combined in resources.combined_lessons
        for lesson_ids in combined.member_lesson_ids
        for lesson_id in lesson_ids
    }
    unavailable = {(item.teacher_id, item.time_slot_id) for item in resources.teacher_unavailability}
    inactive_teachers = {
        item.entity_id
        for item in resources.active_statuses
        if item.entity_type == "teacher" and not item.is_active
    }
    workload_max = {item.teacher_id: item.max_weekly_periods for item in resources.teacher_workload_limits}

    current = list(assignments)
    improved = True
    while improved:
        improved = False
        cross_requirements = sorted(
            {a.class_subject_requirement_id for a in current if rule.is_cross(a)}
        )
        for requirement_id in cross_requirements:
            own = [a for a in current if a.class_subject_requirement_id == requirement_id]
            if any(a.lesson_id in combined_lesson_ids for a in own):
                continue
            slots = {a.time_slot_id for a in own}
            class_id = own[0].class_id
            busy: dict[int, set[int | None]] = defaultdict(set)
            for a in current:
                if a.teacher_id is not None and a.class_subject_requirement_id != requirement_id:
                    busy[a.teacher_id].add(a.time_slot_id)
            for teacher_id in resources.teacher_ids:
                if teacher_id == own[0].teacher_id or rule.is_cross_teacher(teacher_id, class_id):
                    continue
                if teacher_id in inactive_teachers:
                    continue
                if busy[teacher_id] & slots:
                    continue
                if any((teacher_id, slot) in unavailable for slot in slots):
                    continue
                limit = workload_max.get(teacher_id)
                if limit is not None and len(busy[teacher_id]) + len(slots) > limit:
                    continue
                trial = [
                    replace(a, teacher_id=teacher_id)
                    if a.class_subject_requirement_id == requirement_id
                    else a
                    for a in current
                ]
                if all(constraint.validate(trial) for constraint in constraints):
                    current = trial
                    improved = True
                    break
    return current
