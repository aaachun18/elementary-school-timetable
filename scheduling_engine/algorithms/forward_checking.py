"""Forward Checking Scheduler (Task 104) -- the search 自動排課 uses.

Backtracking (backtracking.py, kept as it is) fixes one lesson order up
front and tries every lesson's candidates in time slot order, earliest
first. When every class fills all of its time slots, a wrong choice made
early is only discovered many positions later, and retracting the most
recent positions one by one never reaches it: the search runs into its
limit although a timetable exists. This search differs in four ways:

1. Forward checking. Placing a unit (a lesson, a 連堂 block or a 合併節,
   algorithms/blocks.py) at once removes every candidate of the units
   still waiting that it rules out -- the same teacher, class or room in
   the same time slot, a room that is now full, a teacher now at their
   weekly maximum, another block of the same requirement on that day, a
   different teacher for another lesson of the same requirement (H15). A
   unit left with no candidate is a dead end found immediately, not when
   the search reaches it.
2. Free slot counting. A class (or a lesson's fixed teacher) still needs as
   many different time slots as it has lessons left; when fewer are still
   reachable by its waiting units, the branch is a dead end.
3. Most constrained first, decided anew at every step: the waiting unit
   with the fewest candidates left is placed next.
4. Restarts. A run that has backtracked too often starts over with a new
   order of trying (random, from `seed`). The allowances follow the Luby
   sequence (1, 1, 2, 1, 1, 2, 4, ...) times RESTART_UNIT_BACKTRACKS: mostly
   short runs -- a fresh order usually beats digging deeper into a bad one
   -- with ever longer ones in between, so a long run still happens. The
   same input and seed give the same timetable; a different seed usually a
   different one (the service picks a new seed per run).

Hard constraints are still the constraint classes themselves: every
candidate is first checked alone against them (whatever only depends on
the candidate -- availability, the required teacher and room, fixed and
allowed time slots, ...), the conflicts between two units are then tracked
as "who holds what" (_Candidate), and the finished timetable is checked
once more against the real constraints. A timetable those reject would
mean the tracking above is wrong -- an engine bug, raised, never returned.
After that, H7 (weekly periods) is checked as in Backtracking. A search that stops early (time or node limit) returns no
timetable at all, never a partial one.

導師 rule (algorithms/homeroom.py): when the record has 導師, the search
first runs with the rule as a hard constraint (no other class's lesson
without a required teacher for a 導師), using at most STRICT_TIME_SHARE of
the time and nodes. If that finds no timetable, it runs again without the
rule -- preferring candidates that keep it -- and then keeps lowering the
allowed number of such periods (forward-checked like the workload limit)
while time remains. The rule never makes an otherwise possible timetable
fail: the relaxed search is exactly the search without the rule.
"""

import random
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from scheduling_engine.algorithms.blocks import (
    SchedulingUnit,
    block_constraints,
    build_units,
    iter_unit_candidates,
    weekday_by_slot,
)
from scheduling_engine.algorithms.homeroom import (
    HomeroomRule,
    build_homeroom_rule,
    reduce_cross_homeroom,
)
from scheduling_engine.algorithms.resources import (
    LessonFailure,
    SchedulingResources,
    build_lookup_tables,
    build_real_time_constraints,
    candidate_teacher_ids,
    no_candidate_teacher_violation,
)
from scheduling_engine.constraints.base import BaseConstraint, ConstraintViolation
from scheduling_engine.constraints.weekly_periods import WeeklyPeriodsConstraint
from scheduling_engine.models.domain import LessonAssignment
from scheduling_engine.state import SchedulingState

FailureType = Literal["DEFINITELY_INFEASIBLE", "SEARCH_LIMIT_EXCEEDED", "TIMEOUT"]

# Backtracks a run may make before starting over, times the Luby number of
# the run (see the module docstring).
RESTART_UNIT_BACKTRACKS = 30
# Placements tried in all runs together before giving up.
DEFAULT_MAX_NODES = 1_000_000
# 導師 rule: the share of the time (and nodes) the search with the rule as
# a hard constraint may use before the relaxed search takes over.
STRICT_TIME_SHARE = 0.5

# What a placement holds that no other unit may hold too:
# ("teacher", teacher, slot), ("class", class, slot), ("block_day",
# requirement, weekday) -- different blocks of one requirement on
# different days.
HeldKey = tuple[str, int, int]
# Whose free time slots are counted (point 2): ("class", class) or
# ("teacher", teacher).
Owner = tuple[str, int]


@dataclass
class ForwardCheckingResult:
    """Same shape and meaning as BacktrackingResult (success=False -> state
    None; failure_type None on success and on the post-hoc H7 failure), plus
    the search statistics.

    - DEFINITELY_INFEASIBLE: a run tried everything without being cut off
      for a restart, or a lesson has no candidate teacher at all
      (lesson_failures) -- a certain answer.
    - SEARCH_LIMIT_EXCEEDED: `max_nodes` placements tried in all runs.
    - TIMEOUT: `timeout_seconds` elapsed.
    Neither of the last two says that no timetable exists.
    """

    success: bool
    state: SchedulingState | None
    failure_type: FailureType | None
    lesson_failures: list[LessonFailure]
    post_hoc_violations: list[ConstraintViolation]
    # Placements taken back, in all runs together.
    backtrack_count: int
    # Placements tried, in all runs together.
    node_count: int = 0
    restart_count: int = 0
    seed: int = 0
    elapsed_seconds: float = 0.0
    # 導師 rule: periods in which a 導師 teaches another class's lesson
    # that names no required teacher (0 when the rule held, or on failure),
    # and whether the rule had to be relaxed to find a timetable at all.
    cross_homeroom_periods: int = 0
    homeroom_rule_relaxed: bool = False


@dataclass(frozen=True)
class _Candidate:
    """One way to place a unit, with what it holds while placed."""

    assignments: tuple[LessonAssignment, ...]
    held_keys: frozenset[HeldKey]
    # (room, slot): one use of the room in that slot (a 合併節 counts once).
    room_slots: frozenset[tuple[int, int]]
    # teacher -> periods it adds to the teacher's week.
    teacher_periods: tuple[tuple[int, int], ...]
    # The (class, slot) / (teacher, slot) it would fill: counted for point 2.
    covered_slots: frozenset[tuple[Owner, int]]
    # H15: (requirement, teacher) of its lessons -- every other lesson of
    # the requirement must get the same teacher.
    requirement_teachers: frozenset[tuple[int, int]] = frozenset()
    # 導師 rule: cross-homeroom periods it holds (algorithms/homeroom.py).
    cost: int = 0


@dataclass
class _Unit:
    unit: SchedulingUnit
    candidates: list[_Candidate]
    # Point 2: slots it still needs per owner -- its lessons per class, and
    # per teacher only where every candidate has that teacher.
    needs: dict[Owner, int]


class _Restart(Exception):
    pass


class _Stop(Exception):
    def __init__(self, failure_type: FailureType) -> None:
        super().__init__(failure_type)
        self.failure_type = failure_type


def schedule_forward_checking(
    lessons: list[LessonAssignment],
    resources: SchedulingResources,
    seed: int = 0,
    timeout_seconds: float | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> ForwardCheckingResult:
    start_time = time.monotonic()
    tables = build_lookup_tables(resources)

    # Same pre-flight as Backtracking: a lesson nobody may teach.
    trivial_failures = [
        LessonFailure(
            lesson_id=lesson.lesson_id,
            class_subject_requirement_id=lesson.class_subject_requirement_id,
            reasons=[no_candidate_teacher_violation(lesson, tables)],
        )
        for lesson in lessons
        if not candidate_teacher_ids(lesson, tables)
    ]
    if trivial_failures:
        return ForwardCheckingResult(
            success=False,
            state=None,
            failure_type="DEFINITELY_INFEASIBLE",
            lesson_failures=trivial_failures,
            post_hoc_violations=[],
            backtrack_count=0,
            seed=seed,
            elapsed_seconds=time.monotonic() - start_time,
        )

    constraints: list[BaseConstraint] = [
        *build_real_time_constraints(resources, include_teacher_workload=True),
        *block_constraints(resources),
    ]
    rule = build_homeroom_rule(resources)
    units = _prepare_units(lessons, resources, constraints, rule)
    totals = _Totals()

    def search(budget: int | None, time_limit: float | None, node_limit: int) -> "_Search":
        found = _Search(
            units,
            resources,
            random.Random(seed),
            start_time,
            time_limit,
            node_limit,
            budget=budget,
        )
        found.failure_type = found.run()
        totals.add(found)
        return found

    def failed(kind: FailureType | None, violations: list[ConstraintViolation]) -> ForwardCheckingResult:
        return ForwardCheckingResult(
            success=False,
            state=None,
            failure_type=kind,
            lesson_failures=[],
            post_hoc_violations=violations,
            backtrack_count=totals.backtrack_count,
            node_count=totals.node_count,
            restart_count=totals.restart_count,
            seed=seed,
            elapsed_seconds=time.monotonic() - start_time,
        )

    relaxed = False
    if not any(candidate.cost for unit in units for candidate in unit.candidates):
        # No 導師 rule to keep (none, or nobody could break it): one search,
        # exactly as before.
        plain = search(None, timeout_seconds, max_nodes)
        if plain.failure_type is not None:
            return failed(plain.failure_type, [])
        assignments = plain.placed_assignments()
    else:
        strict = search(
            0,
            None if timeout_seconds is None else timeout_seconds * STRICT_TIME_SHARE,
            int(max_nodes * STRICT_TIME_SHARE),
        )
        if strict.failure_type is None:
            assignments = strict.placed_assignments()
        else:
            relaxed = True
            found = _minimize_cross_homeroom(
                search, start_time, resources, rule, constraints, timeout_seconds, max_nodes, totals
            )
            if isinstance(found, str):
                return failed(found, [])
            assignments = found

    state = SchedulingState()
    for assignment in assignments:
        state.add_assignment(assignment)
    broken = [violation for c in constraints for violation in c.explain_violations(state.assignments)]
    if broken:
        raise RuntimeError(
            f"Forward checking produced a timetable the hard constraints reject ({broken[0].type}) "
            "-- engine bug, no timetable returned."
        )
    post_hoc_violations = WeeklyPeriodsConstraint(resources.requirement_periods).explain_violations(
        state.assignments
    )
    if post_hoc_violations:
        return failed(None, post_hoc_violations)
    return ForwardCheckingResult(
        success=True,
        state=state,
        failure_type=None,
        lesson_failures=[],
        post_hoc_violations=[],
        backtrack_count=totals.backtrack_count,
        node_count=totals.node_count,
        restart_count=totals.restart_count,
        seed=seed,
        elapsed_seconds=time.monotonic() - start_time,
        cross_homeroom_periods=rule.count(state.assignments),
        homeroom_rule_relaxed=relaxed,
    )


@dataclass
class _Totals:
    """Search statistics of every search one call runs, added up."""

    backtrack_count: int = 0
    node_count: int = 0
    restart_count: int = 0

    def add(self, search: "_Search") -> None:
        self.backtrack_count += search.backtrack_count
        self.node_count += search.node_count
        self.restart_count += search.restart_count


def _minimize_cross_homeroom(
    search: Callable[[int | None, float | None, int], "_Search"],
    start_time: float,
    resources: SchedulingResources,
    rule: HomeroomRule,
    constraints: list[BaseConstraint],
    timeout_seconds: float | None,
    max_nodes: int,
    totals: _Totals,
) -> list[LessonAssignment] | FailureType:
    """The 導師 rule could not be kept (or not within its share of the
    time): find any timetable, then as few cross-homeroom periods as the
    remaining time and nodes allow. Returns the best timetable found, or
    the failure of the search without the rule (then there is no timetable
    within the limits, 導師 rule or not)."""
    first = search(None, timeout_seconds, max_nodes - totals.node_count)
    if first.failure_type is not None:
        return first.failure_type
    best = reduce_cross_homeroom(first.placed_assignments(), resources, rule, constraints)
    best_cost = rule.count(best)
    while best_cost > 0 and totals.node_count < max_nodes:
        if timeout_seconds is not None and time.monotonic() - start_time >= timeout_seconds:
            break
        tighter = search(best_cost - 1, timeout_seconds, max_nodes - totals.node_count)
        if tighter.failure_type is not None:
            # Proven impossible, or out of time / nodes: keep the best.
            break
        best = reduce_cross_homeroom(tighter.placed_assignments(), resources, rule, constraints)
        best_cost = rule.count(best)
    return best


def _prepare_units(
    lessons: list[LessonAssignment],
    resources: SchedulingResources,
    constraints: list[BaseConstraint],
    rule: HomeroomRule,
) -> list[_Unit]:
    """Every unit with the candidates that pass every constraint on their
    own -- the only constraint check that is not about two units."""
    tables = build_lookup_tables(resources)
    weekday_of = weekday_by_slot(resources)
    requirement_of_block_lesson = {
        lesson_id: block.class_subject_requirement_id
        for block in resources.lesson_blocks
        for lesson_id in block.lesson_ids
    }
    prepared: list[_Unit] = []
    for unit in build_units(lessons, resources):
        candidates = [
            _describe(candidate, weekday_of, requirement_of_block_lesson, rule)
            for candidate in iter_unit_candidates(unit, resources, tables)
            if all(constraint.validate(list(candidate)) for constraint in constraints)
        ]
        prepared.append(_Unit(unit, candidates, _needs(unit, candidates)))
    return prepared


def _describe(
    assignments: tuple[LessonAssignment, ...],
    weekday_of: dict[int, int],
    requirement_of_block_lesson: dict[int, int],
    rule: HomeroomRule,
) -> _Candidate:
    held: set[HeldKey] = set()
    room_slots: set[tuple[int, int]] = set()
    teacher_slots: dict[int, set[int]] = defaultdict(set)
    covered: set[tuple[Owner, int]] = set()
    requirement_teachers = {
        (assignment.class_subject_requirement_id, assignment.teacher_id)
        for assignment in assignments
        if assignment.teacher_id is not None
    }
    for assignment in assignments:
        slot = assignment.time_slot_id
        if slot is None:
            continue
        held.add(("class", assignment.class_id, slot))
        covered.add((("class", assignment.class_id), slot))
        if assignment.teacher_id is not None:
            held.add(("teacher", assignment.teacher_id, slot))
            teacher_slots[assignment.teacher_id].add(slot)
            covered.add((("teacher", assignment.teacher_id), slot))
        if assignment.room_id is not None:
            room_slots.add((assignment.room_id, slot))
        requirement_id = requirement_of_block_lesson.get(assignment.lesson_id)
        if requirement_id is not None and slot in weekday_of:
            held.add(("block_day", requirement_id, weekday_of[slot]))
    return _Candidate(
        assignments=assignments,
        held_keys=frozenset(held),
        room_slots=frozenset(room_slots),
        teacher_periods=tuple(sorted((teacher, len(slots)) for teacher, slots in teacher_slots.items())),
        covered_slots=frozenset(covered),
        requirement_teachers=frozenset(requirement_teachers),
        cost=rule.count(assignments),
    )


def _needs(unit: SchedulingUnit, candidates: list[_Candidate]) -> dict[Owner, int]:
    needs: dict[Owner, int] = defaultdict(int)
    for lesson in unit.lessons:
        needs[("class", lesson.class_id)] += 1
    if candidates:
        shared = set(candidates[0].teacher_periods)
        for candidate in candidates[1:]:
            shared &= set(candidate.teacher_periods)
        for teacher, periods in shared:
            needs[("teacher", teacher)] += periods
    return dict(needs)


def luby(index: int) -> int:
    """The index-th (from 1) number of the Luby sequence 1, 1, 2, 1, 1, 2,
    4, 1, 1, 2, 1, 1, 2, 4, 8, ...: every run of 2^k - 1 numbers ends in
    2^(k-1), after the whole sequence before it once more."""
    size = 1
    while size < index + 1:
        size = size * 2 + 1
    while size > 1:
        half = size // 2
        if index == size:
            return (size + 1) // 2
        if index > half:
            index -= half
        size = half
    return 1


@dataclass
class _Frame:
    """One unit being placed: the candidates to try, in order."""

    unit_index: int
    options: list[int]
    next_option: int = 0
    trail_mark: int | None = None


@dataclass
class _Search:
    units: list[_Unit]
    resources: SchedulingResources
    rng: random.Random
    start_time: float
    timeout_seconds: float | None
    max_nodes: int
    # 導師 rule: the most cross-homeroom periods allowed (None: no limit).
    budget: int | None = None
    failure_type: FailureType | None = None
    backtrack_count: int = 0
    node_count: int = 0
    restart_count: int = 0
    # Filled per run by _reset().
    alive: list[list[bool]] = field(default_factory=list)
    alive_count: list[int] = field(default_factory=list)
    placed: list[int | None] = field(default_factory=list)
    # (unit, candidate) taken out, in order -- undone back to a mark.
    trail: list[tuple[int, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.room_capacity = {item.room_id: item.max_classes for item in self.resources.room_capacities}
        self.workload_max = {
            item.teacher_id: item.max_weekly_periods for item in self.resources.teacher_workload_limits
        }
        # Who might hold what: key -> [(unit, candidate)].
        self.by_held_key: dict[HeldKey, list[tuple[int, int]]] = defaultdict(list)
        self.by_room_slot: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
        self.by_teacher: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
        # H15: requirement -> [(unit, candidate, teacher)].
        self.by_requirement: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
        for unit_index, unit in enumerate(self.units):
            for candidate_index, candidate in enumerate(unit.candidates):
                for key in candidate.held_keys:
                    self.by_held_key[key].append((unit_index, candidate_index))
                for room_slot in candidate.room_slots:
                    self.by_room_slot[room_slot].append((unit_index, candidate_index))
                for teacher, periods in candidate.teacher_periods:
                    self.by_teacher[teacher].append((unit_index, candidate_index, periods))
                for requirement, teacher in candidate.requirement_teachers:
                    self.by_requirement[requirement].append((unit_index, candidate_index, teacher))
        # 導師 rule: [(unit, candidate, cost)] of every candidate with a cost.
        self.costly: list[tuple[int, int, int]] = [
            (unit_index, candidate_index, candidate.cost)
            for unit_index, unit in enumerate(self.units)
            for candidate_index, candidate in enumerate(unit.candidates)
            if candidate.cost > 0
        ]

    # --- one run --------------------------------------------------------

    def run(self) -> FailureType | None:
        """None: every unit placed (see placed_assignments())."""
        if any(not unit.candidates for unit in self.units):
            return "DEFINITELY_INFEASIBLE"
        while True:
            self._reset()
            if any(count == 0 for count in self.alive_count):
                return "DEFINITELY_INFEASIBLE"
            allowance = luby(self.restart_count + 1) * RESTART_UNIT_BACKTRACKS
            try:
                return None if self._run_once(allowance) else "DEFINITELY_INFEASIBLE"
            except _Restart:
                self.restart_count += 1
            except _Stop as stop:
                return stop.failure_type

    def placed_assignments(self) -> list[LessonAssignment]:
        return [
            assignment
            for unit_index, candidate_index in enumerate(self.placed)
            if candidate_index is not None
            for assignment in self.units[unit_index].candidates[candidate_index].assignments
        ]

    def _reset(self) -> None:
        # 導師 rule: a candidate over the budget on its own is never alive.
        self.alive = [
            [self.budget is None or candidate.cost <= self.budget for candidate in unit.candidates]
            for unit in self.units
        ]
        self.alive_count = [sum(alive) for alive in self.alive]
        self.cost = 0
        self.placed = [None] * len(self.units)
        self.trail = []
        self.waiting = set(range(len(self.units)))
        self.room_use: dict[tuple[int, int], int] = defaultdict(int)
        self.teacher_load: dict[int, int] = defaultdict(int)
        # Point 2: candidates still able to fill each (owner, slot), how
        # many slots each owner can still fill, and how many it needs.
        self.cover_count: dict[tuple[Owner, int], int] = defaultdict(int)
        self.coverable: dict[Owner, int] = defaultdict(int)
        self.need: dict[Owner, int] = defaultdict(int)
        for unit_index, unit in enumerate(self.units):
            for owner, count in unit.needs.items():
                self.need[owner] += count
            for candidate_index, candidate in enumerate(unit.candidates):
                if not self.alive[unit_index][candidate_index]:
                    continue
                for covered in candidate.covered_slots:
                    if self.cover_count[covered] == 0:
                        self.coverable[covered[0]] += 1
                    self.cover_count[covered] += 1
        # Ties in "fewest candidates left" are broken differently per run.
        self.tie_break = [self.rng.random() for _ in self.units]

    def _run_once(self, allowance: int) -> bool:
        """True: every unit placed. False: everything tried (no timetable
        exists). _Restart: more than `allowance` backtracks this run."""
        run_backtracks = 0
        stack: list[_Frame] = []
        if not self.waiting:
            return True
        stack.append(self._frame_for(self._most_constrained()))
        while stack:
            frame = stack[-1]
            if frame.trail_mark is not None:
                self._take_back(frame)
            if frame.next_option >= len(frame.options):
                stack.pop()
                if not stack:
                    return False
                self.backtrack_count += 1
                run_backtracks += 1
                if run_backtracks > allowance:
                    raise _Restart
                continue
            candidate_index = frame.options[frame.next_option]
            frame.next_option += 1
            self._check_limits()
            self.node_count += 1
            frame.trail_mark = len(self.trail)
            if not self._place(frame.unit_index, candidate_index):
                continue
            if not self.waiting:
                return True
            stack.append(self._frame_for(self._most_constrained()))
        return False

    def _check_limits(self) -> None:
        if self.timeout_seconds is not None and time.monotonic() - self.start_time > self.timeout_seconds:
            raise _Stop("TIMEOUT")
        if self.node_count >= self.max_nodes:
            raise _Stop("SEARCH_LIMIT_EXCEEDED")

    def _most_constrained(self) -> int:
        return min(self.waiting, key=lambda index: (self.alive_count[index], self.tie_break[index]))

    def _frame_for(self, unit_index: int) -> _Frame:
        alive = self.alive[unit_index]
        options = [index for index, is_alive in enumerate(alive) if is_alive]
        self.rng.shuffle(options)
        # 導師 rule: candidates keeping it first (a stable sort: without
        # costs the shuffled order is unchanged).
        candidates = self.units[unit_index].candidates
        options.sort(key=lambda index: candidates[index].cost)
        return _Frame(unit_index, options)

    # --- placing and taking back ----------------------------------------

    def _place(self, unit_index: int, candidate_index: int) -> bool:
        """Place the candidate and take out everything it rules out. False:
        a dead end (the caller takes it back either way)."""
        unit = self.units[unit_index]
        candidate = unit.candidates[candidate_index]
        self.placed[unit_index] = candidate_index
        self.waiting.discard(unit_index)
        for owner, count in unit.needs.items():
            self.need[owner] -= count
        # The unit no longer waits: none of its candidates count any more.
        for index, is_alive in enumerate(self.alive[unit_index]):
            if is_alive:
                self._remove(unit_index, index)

        for key in candidate.held_keys:
            for other_unit, other_index in self.by_held_key[key]:
                self._remove_if_waiting(other_unit, other_index)
        # H15: the requirement's other lessons get this teacher too.
        for requirement, teacher in candidate.requirement_teachers:
            for other_unit, other_index, other_teacher in self.by_requirement[requirement]:
                if other_teacher != teacher:
                    self._remove_if_waiting(other_unit, other_index)
        for room_slot in candidate.room_slots:
            self.room_use[room_slot] += 1
            if self.room_use[room_slot] >= self.room_capacity.get(room_slot[0], 1):
                for other_unit, other_index in self.by_room_slot[room_slot]:
                    self._remove_if_waiting(other_unit, other_index)
        for teacher, periods in candidate.teacher_periods:
            self.teacher_load[teacher] += periods
            limit = self.workload_max.get(teacher)
            if limit is None:
                continue
            for other_unit, other_index, other_periods in self.by_teacher[teacher]:
                if self.teacher_load[teacher] + other_periods > limit:
                    self._remove_if_waiting(other_unit, other_index)
        # 導師 rule: like the workload limit, for the cross-homeroom budget.
        self.cost += candidate.cost
        if self.budget is not None and candidate.cost > 0:
            remaining = self.budget - self.cost
            for other_unit, other_index, other_cost in self.costly:
                if other_cost > remaining:
                    self._remove_if_waiting(other_unit, other_index)

        if any(self.alive_count[index] == 0 for index in self.waiting):
            return False
        return all(self.coverable[owner] >= count for owner, count in self.need.items() if count > 0)

    def _take_back(self, frame: _Frame) -> None:
        assert frame.trail_mark is not None
        unit_index = frame.unit_index
        candidate_index = self.placed[unit_index]
        while len(self.trail) > frame.trail_mark:
            self._restore(*self.trail.pop())
        frame.trail_mark = None
        if candidate_index is None:
            return
        unit = self.units[unit_index]
        candidate = unit.candidates[candidate_index]
        self.placed[unit_index] = None
        self.waiting.add(unit_index)
        for owner, count in unit.needs.items():
            self.need[owner] += count
        for room_slot in candidate.room_slots:
            self.room_use[room_slot] -= 1
        for teacher, periods in candidate.teacher_periods:
            self.teacher_load[teacher] -= periods
        self.cost -= candidate.cost

    def _remove_if_waiting(self, unit_index: int, candidate_index: int) -> None:
        if unit_index in self.waiting and self.alive[unit_index][candidate_index]:
            self._remove(unit_index, candidate_index)

    def _remove(self, unit_index: int, candidate_index: int) -> None:
        self.alive[unit_index][candidate_index] = False
        self.alive_count[unit_index] -= 1
        self.trail.append((unit_index, candidate_index))
        for covered in self.units[unit_index].candidates[candidate_index].covered_slots:
            self.cover_count[covered] -= 1
            if self.cover_count[covered] == 0:
                self.coverable[covered[0]] -= 1

    def _restore(self, unit_index: int, candidate_index: int) -> None:
        self.alive[unit_index][candidate_index] = True
        self.alive_count[unit_index] += 1
        for covered in self.units[unit_index].candidates[candidate_index].covered_slots:
            if self.cover_count[covered] == 0:
                self.coverable[covered[0]] += 1
            self.cover_count[covered] += 1
