import { useMemo, useState, type DragEvent, type ReactElement } from "react";
import { timeSlotKey, type EnrichedSchedule } from "../hooks/useTimetableData";
import { canMoveLessonTo, canSwapLessons, lessonTargetId } from "../utils/lessonDrop";
import {
  blockGroupKey,
  blockGroupMemberIds,
  buildBlockLinks,
  type BlockLink,
} from "../utils/lessonBlocks";
import {
  NO_MARK,
  candidateDescription,
  candidateLabel,
  swapMarkKey,
  type CandidateAction,
  type CandidateMark,
  type CandidateMarks,
} from "../utils/moveCandidates";
import { formatPeriodHeader, type PeriodDisplay, type PeriodDisplayMap } from "../utils/periodDisplay";
import { formatTimeSlotLabel, formatWeekday } from "../utils/timeSlotFormat";
import type { TimetableViewMode } from "../utils/violationLocate";
import type { Lesson } from "../types/lesson";
import type { TimeSlot } from "../types/timeSlot";
import {
  BADGE_NEUTRAL,
  BLOCK_BAR_BASE,
  BLOCK_BAR_BOTTOM_END,
  BLOCK_BAR_BOTTOM_JOINED,
  BLOCK_BAR_TOP_END,
  BLOCK_BAR_TOP_JOINED,
  CANDIDATE_ICON_BLOCKED,
  CANDIDATE_ICON_CONFLICT,
  CANDIDATE_ICON_SAFE,
  CELL_MOVE_TARGET,
  DROP_TARGET_BLOCKED,
  DROP_TARGET_OK,
  DROP_TARGET_RANGE,
  DROP_STRIP,
  DROP_ZONE,
  DROP_ZONE_BLOCKED,
  LESSON_BUTTON,
  LESSON_BUTTON_DRAGGING,
  LESSON_BUTTON_DROP_OK,
  LESSON_BUTTON_SELECTED,
  MOVE_TARGET_STRIP,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TD_ADJUSTED,
  TD_CANDIDATE_BLOCKED,
  TD_CANDIDATE_CONFLICT,
  TD_CANDIDATE_SAFE,
  TD_HIGHLIGHT,
  TD_NON_TEACHING,
  TD_NON_TEACHING_BASE,
  TH,
  TIMETABLE_ROW_HEADER,
  TIMETABLE_ROW_HEADER_NON_TEACHING,
  TR_HOVER,
} from "../styles/ui";

const WEEKDAYS = [1, 2, 3, 4, 5];

// Task 71: the only thing a drag carries -- the full lesson is looked up
// from `schedules` on drop.
const DRAG_DATA_TYPE = "text/plain";

// Task 69: present only in edit mode. Without it the grid renders exactly
// as the read-only timetable always has.
export interface TimetableGridEditProps {
  selected: EnrichedSchedule | null;
  // A preview/save request is in flight: nothing can be clicked or dragged.
  disabled: boolean;
  // For the 「固定」 marker (Lesson.fixed_time_slot_id).
  lessonById: Map<number, Lesson>;
  onLessonClick: (lesson: EnrichedSchedule) => void;
  onMoveHere: (timeSlot: TimeSlot) => void;
  // Task 71: drag & drop is just another way to pick the same move/swap --
  // these hand it to the same preview flow as the click handlers above.
  // Task 84: the page is told which lesson is dragged (called a tick after
  // dragstart, never inside it) and when the drag ends, to show its
  // candidate marks meanwhile.
  onDragStartLesson: (lesson: EnrichedSchedule) => void;
  onDragEndLesson: () => void;
  // Task 84: marks for the selected / dragged lesson, or null for none.
  candidateMarks: CandidateMarks | null;
  onDropOnCell: (lesson: EnrichedSchedule, timeSlot: TimeSlot) => void;
  onDropOnLesson: (lesson: EnrichedSchedule, other: EnrichedSchedule) => void;
  // Task 93: an unscheduled card (the 「未排入課程」 panel) is selected or
  // being dragged -- every teaching cell is then a place target (its
  // 「放到這裡」, or a drop), and candidateMarks are that card's. null
  // otherwise: the grid works exactly as before. isDragging is reported a
  // tick after the card's dragstart, like a lesson's.
  placing: { isDragging: boolean } | null;
  onPlaceOnCell: (timeSlot: TimeSlot) => void;
}

interface TimetableGridProps {
  periods: number[];
  // Task 78: how each period is named on screen (teaching number or the
  // non-teaching row's name), built from all time slots.
  periodDisplay: PeriodDisplayMap;
  schedules: EnrichedSchedule[];
  viewMode: TimetableViewMode;
  targetId: number;
  timeSlotByWeekdayAndPeriod: Map<string, TimeSlot>;
  // Task 68: the cell 「在課表中查看」 points at.
  highlightedTimeSlotId: number | null;
  // Task 71 fix: the cell a just-saved move/swap landed in; the parent only
  // passes it in edit mode.
  adjustedTimeSlotId: number | null;
  edit: TimetableGridEditProps | null;
}

// What is under the pointer during a drag: a cell or one lesson button.
type DragHover = { kind: "cell"; key: string } | { kind: "lesson"; scheduleId: number };

function sameHover(a: DragHover | null, b: DragHover | null): boolean {
  if (a === null || b === null) {
    return a === b;
  }
  if (a.kind === "cell" && b.kind === "cell") {
    return a.key === b.key;
  }
  return a.kind === "lesson" && b.kind === "lesson" && a.scheduleId === b.scheduleId;
}

// Task 84 / Task 85: the small icon in a cell's top-right corner for its
// move mark (null for none/unavailable). ✓ / ✕ differ in shape, not just
// colour; the label and the full description (with up to 3 reasons) are
// the title and the accessible name.
function CandidateIcon({
  mark,
  action,
}: {
  mark: CandidateMark;
  action: CandidateAction;
}): ReactElement | null {
  const label = candidateLabel(mark, action);
  const description = candidateDescription(mark, action);
  if (label === null || description === null) {
    return null;
  }
  const isSafe = mark.status === "safe";
  const isBlocked = mark.status === "blocked";
  return (
    <span
      className={isSafe ? CANDIDATE_ICON_SAFE : isBlocked ? CANDIDATE_ICON_BLOCKED : CANDIDATE_ICON_CONFLICT}
      title={`${label}：${description}`}
      aria-label={`${label}：${description}`}
      role="img"
    >
      {isSafe ? "✓" : isBlocked ? "⊘" : "✕"}
    </span>
  );
}

// Task 90: the bar along the left edge of a lesson block's cell; it joins
// the cell above / below when the block's neighbouring lesson is there.
function BlockBar({ link }: { link: BlockLink }): ReactElement {
  return (
    <span
      aria-hidden="true"
      data-block-bar=""
      className={`${BLOCK_BAR_BASE} ${link.above ? BLOCK_BAR_TOP_JOINED : BLOCK_BAR_TOP_END} ${
        link.below ? BLOCK_BAR_BOTTOM_JOINED : BLOCK_BAR_BOTTOM_END
      }`}
    />
  );
}

// What a cell shows besides the subject name -- "the other party" for
// whichever axis isn't the one currently being browsed. Room view shows
// the same pairing as teacher view (subject + class): which class is
// occupying the room is the most room-relevant question; see Task 34's
// report for this being my own reasonable extension, not spelled out in
// the spec.
function cellDetailOf(row: EnrichedSchedule, viewMode: TimetableViewMode): string {
  if (viewMode === "class") {
    return row.teacherName ?? "未指定教師";
  }
  return row.className;
}

function lessonAriaLabel(lesson: EnrichedSchedule, selected: EnrichedSchedule | null): string {
  // Task 90: a lesson block's lessons say so (the bar is visual only).
  const name = `${lesson.className} ${lesson.subjectName}${blockGroupKey(lesson) !== null ? "（連堂）" : ""}`;
  if (selected === null) {
    return `選取 ${name}`;
  }
  if (selected.scheduleId === lesson.scheduleId) {
    return `取消選取 ${name}`;
  }
  return `與已選取的 ${selected.className} ${selected.subjectName} 對調：${name}`;
}

type LessonDragState = "dragging" | "dropOk" | null;

const LESSON_CLASS_BY_DRAG_STATE: Record<Exclude<LessonDragState, null>, string> = {
  dragging: LESSON_BUTTON_DRAGGING,
  dropOk: LESSON_BUTTON_DROP_OK,
};

// Task 69: one lesson as a button (edit mode only). Task 71: also the drag
// source, and a drop target for swapping with it.
function LessonButton({
  lesson,
  viewMode,
  edit,
  dragState,
  isInSelectedGroup,
  candidateMark,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}: {
  lesson: EnrichedSchedule;
  viewMode: TimetableViewMode;
  edit: TimetableGridEditProps;
  dragState: LessonDragState;
  // Task 90: another lesson of the selected lesson's block -- shown
  // selected too, so the whole block reads as one.
  isInSelectedGroup: boolean;
  // Task 84: what swapping the selected / dragged lesson with this one
  // would do.
  candidateMark: CandidateMark;
  onDragStart: (event: DragEvent<HTMLButtonElement>) => void;
  onDragEnd: () => void;
  onDragOver: (event: DragEvent<HTMLButtonElement>) => void;
  onDrop: (event: DragEvent<HTMLButtonElement>) => void;
}): ReactElement {
  const isSelected = edit.selected?.scheduleId === lesson.scheduleId;
  const isFixed = (edit.lessonById.get(lesson.lessonId)?.fixed_time_slot_id ?? null) !== null;
  const className =
    dragState !== null
      ? LESSON_CLASS_BY_DRAG_STATE[dragState]
      : isSelected || isInSelectedGroup
        ? LESSON_BUTTON_SELECTED
        : LESSON_BUTTON;
  const candidateText = candidateDescription(candidateMark, "swap");
  const ariaLabel = lessonAriaLabel(lesson, edit.selected);
  return (
    <button
      type="button"
      onClick={() => edit.onLessonClick(lesson)}
      disabled={edit.disabled}
      // A fixed lesson can be dragged too -- 「固定」 is only a marker; the
      // preview reports a FIXED_TIME_SLOT_MISMATCH if it's moved away.
      draggable={!edit.disabled}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
      aria-pressed={isSelected}
      aria-label={candidateText === null ? ariaLabel : `${ariaLabel}（${candidateText}）`}
      title={candidateText ?? undefined}
      className={className}
      data-schedule-id={lesson.scheduleId}
    >
      <span className="font-medium text-gray-900">
        {lesson.subjectName}
        {isFixed && (
          <span className={`${BADGE_NEUTRAL} ml-1`} title="這堂課設有固定時段">
            固定
          </span>
        )}
      </span>
      <span className="text-gray-500">{cellDetailOf(lesson, viewMode)}</span>
      {isSelected && <span className="text-xs font-semibold text-blue-700">✓ 已選取</span>}
    </button>
  );
}

// The weekly grid for one class/teacher/room: periods down, Monday-Friday
// across. Extracted from TimetableView.tsx in Task 69 to add edit mode.
export default function TimetableGrid({
  periods,
  periodDisplay,
  schedules,
  viewMode,
  targetId,
  timeSlotByWeekdayAndPeriod,
  highlightedTimeSlotId,
  adjustedTimeSlotId,
  edit,
}: TimetableGridProps): ReactElement {
  // --- Task 71: drag & drop (edit mode only). Native HTML5 events; the
  // drag only carries the scheduleId. Which drop targets are allowed is
  // decided from `dragging` (dataTransfer can't be read until drop). ---
  const [dragging, setDragging] = useState<EnrichedSchedule | null>(null);
  const [dragHover, setDragHover] = useState<DragHover | null>(null);

  // --- Task 90: lesson blocks (連堂). The bar joining a block's cells, in
  // every mode; in edit mode the dragged / selected lesson's whole block is
  // styled as dragged / selected, and while dragging, the cells where the
  // whole block would land (move-candidates' block_members) are outlined.
  const blockLinks = useMemo(() => buildBlockLinks(schedules), [schedules]);
  const draggingGroup = useMemo(
    () => (dragging === null ? null : blockGroupMemberIds(schedules, dragging)),
    [schedules, dragging],
  );
  const selectedLesson = edit?.selected ?? null;
  const selectedGroup = useMemo(
    () => (selectedLesson === null ? null : blockGroupMemberIds(schedules, selectedLesson)),
    [schedules, selectedLesson],
  );
  const marks = edit?.candidateMarks ?? null;
  // Task 93: an unscheduled card is the drag source instead of a lesson.
  const isPlacingDrag = dragging === null && edit?.placing?.isDragging === true;
  const isDragActive = dragging !== null || isPlacingDrag;
  const markAction: CandidateAction = (edit?.placing ?? null) !== null ? "place" : "move";
  const timeSlotById = useMemo(
    () => new Map(Array.from(timeSlotByWeekdayAndPeriod.values(), (slot) => [slot.id, slot])),
    [timeSlotByWeekdayAndPeriod],
  );

  // Where the current drag may be dropped: a lesson moves (as before); a
  // card goes into any teaching cell (the backend decides the rest).
  function canDropAt(timeSlot: TimeSlot | undefined): timeSlot is TimeSlot {
    if (dragging !== null) {
      return canMoveLessonTo(dragging, timeSlot);
    }
    return isPlacingDrag && timeSlot !== undefined && timeSlot.is_teaching_period;
  }

  // The cells the dragged block would land in for the target under the
  // pointer (empty for a single lesson, or a target it can't go to).
  function landingRange(): ReadonlySet<number> {
    if (!isDragActive || dragHover === null || marks === null) {
      return new Set();
    }
    if (dragHover.kind === "cell") {
      const slot = timeSlotByWeekdayAndPeriod.get(dragHover.key);
      return new Set(slot === undefined ? [] : (marks.cellRanges.get(slot.id) ?? []));
    }
    const target = schedules.find((schedule) => schedule.scheduleId === dragHover.scheduleId);
    return new Set(
      target === undefined
        ? []
        : (marks.swapRanges.get(swapMarkKey(target.timeSlotId, target.scheduleId)) ?? []),
    );
  }
  const landing = landingRange();

  function swapMarkOf(lesson: EnrichedSchedule): CandidateMark {
    return marks === null ? NO_MARK : (marks.swaps.get(swapMarkKey(lesson.timeSlotId, lesson.scheduleId)) ?? NO_MARK);
  }

  function endDrag(): void {
    setDragging(null);
    setDragHover(null);
    edit?.onDragEndLesson();
  }

  // dragover fires many times a second -- only re-render on a change.
  function updateHover(next: DragHover): void {
    setDragHover((previous) => (sameHover(previous, next) ? previous : next));
  }

  function draggedLessonOf(event: DragEvent): EnrichedSchedule | undefined {
    const scheduleId = Number(event.dataTransfer.getData(DRAG_DATA_TYPE));
    return schedules.find((schedule) => schedule.scheduleId === scheduleId);
  }

  function handleLessonDragStart(lesson: EnrichedSchedule, event: DragEvent<HTMLButtonElement>): void {
    if (edit === null || edit.disabled) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.setData(DRAG_DATA_TYPE, String(lesson.scheduleId));
    event.dataTransfer.effectAllowed = "move";
    // Deferred one tick: changing the dragged element's look (or removing
    // the click flow's 「移到這裡」 buttons) inside dragstart itself can make
    // some browsers cancel the drag.
    window.setTimeout(() => {
      setDragging(lesson);
      edit.onDragStartLesson(lesson);
    }, 0);
  }

  // A drop is only accepted (preventDefault on dragover) where allowed;
  // elsewhere the browser shows its "not allowed" cursor.
  function handleLessonDragOver(target: EnrichedSchedule, event: DragEvent<HTMLButtonElement>): void {
    // A lesson it can't swap with (itself, or one in its own time slot)
    // lies in the dragged lesson's own cell: let the event reach the cell,
    // which marks the whole cell as not droppable.
    if (dragging === null || !canSwapLessons(dragging, target)) {
      return;
    }
    // The lesson, not the cell around it, is the target.
    event.stopPropagation();
    updateHover({ kind: "lesson", scheduleId: target.scheduleId });
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }

  function handleLessonDrop(target: EnrichedSchedule, event: DragEvent<HTMLButtonElement>): void {
    event.preventDefault();
    event.stopPropagation();
    const lesson = draggedLessonOf(event);
    const wasPlacing = isPlacingDrag;
    endDrag();
    if (edit !== null && !edit.disabled && lesson !== undefined && canSwapLessons(lesson, target)) {
      edit.onDropOnLesson(lesson, target);
      return;
    }
    // Task 93: a card dropped on a lesson goes into that lesson's cell
    // (always refused there -- the class has a lesson -- with the reason).
    const slot = target.timeSlotId === null ? undefined : timeSlotById.get(target.timeSlotId);
    if (edit !== null && !edit.disabled && lesson === undefined && wasPlacing && slot !== undefined) {
      edit.onPlaceOnCell(slot);
    }
  }

  function handleCellDragOver(
    key: string,
    timeSlot: TimeSlot | undefined,
    event: DragEvent<HTMLTableCellElement>,
  ): void {
    if (!isDragActive) {
      return;
    }
    updateHover({ kind: "cell", key });
    if (canDropAt(timeSlot)) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    } else {
      event.dataTransfer.dropEffect = "none";
    }
  }

  function handleCellDrop(timeSlot: TimeSlot | undefined, event: DragEvent<HTMLTableCellElement>): void {
    event.preventDefault();
    const lesson = draggedLessonOf(event);
    const canPlace = lesson === undefined && canDropAt(timeSlot);
    endDrag();
    if (edit !== null && !edit.disabled && lesson !== undefined && canMoveLessonTo(lesson, timeSlot)) {
      edit.onDropOnCell(lesson, timeSlot);
    } else if (edit !== null && !edit.disabled && canPlace && timeSlot !== undefined) {
      edit.onPlaceOnCell(timeSlot);
    }
  }

  // Leaving the table altogether clears the hover hint.
  function handleTableDragLeave(event: DragEvent<HTMLTableElement>): void {
    const next = event.relatedTarget;
    if (!(next instanceof Node) || !event.currentTarget.contains(next)) {
      setDragHover(null);
    }
  }

  // The drop hint for a cell under the pointer, if any; null otherwise.
  function cellDropClass(key: string, timeSlot: TimeSlot | undefined): string | null {
    if (!isDragActive) {
      return null;
    }
    if (dragHover?.kind !== "cell" || dragHover.key !== key) {
      // Task 90: another cell the dragged block would land in.
      return timeSlot !== undefined && landing.has(timeSlot.id) ? DROP_TARGET_RANGE : null;
    }
    const isBlocked =
      timeSlot !== undefined && marks?.cells.get(timeSlot.id)?.status === "blocked";
    return canDropAt(timeSlot) && !isBlocked ? DROP_TARGET_OK : DROP_TARGET_BLOCKED;
  }

  function lessonDragState(lesson: EnrichedSchedule): LessonDragState {
    if (dragging === null) {
      return null;
    }
    if (dragging.scheduleId === lesson.scheduleId || draggingGroup?.has(lesson.scheduleId) === true) {
      return "dragging";
    }
    if (
      dragHover?.kind === "lesson" &&
      dragHover.scheduleId === lesson.scheduleId &&
      swapMarkOf(lesson).status !== "blocked"
    ) {
      return "dropOk";
    }
    return null;
  }

  // Task 35.5: teaching/non-teaching status and label are decided per
  // CELL (this exact weekday+period's own TimeSlot) -- the same period can
  // be "早自習" on Monday and "導師時間" on Wednesday, and each cell shows
  // its own name. Task 78: in a NON-teaching row (no weekday teaches at
  // this period, utils/periodDisplay.ts) every cell is non-teaching, even a
  // weekday with no TimeSlot record at all (e.g. 放學 exists only on
  // Monday); it falls back to the row's name. In a teaching row a missing
  // record is still an ordinary (empty) teaching cell.
  function cellLabelOf(timeSlot: TimeSlot | undefined, rowDisplay: PeriodDisplay | undefined): string | null {
    if (rowDisplay?.kind === "nonTeaching") {
      return timeSlot?.label ?? rowDisplay.label;
    }
    if (timeSlot === undefined || timeSlot.is_teaching_period) {
      return null;
    }
    return timeSlot.label ?? "非教學時段";
  }

  // Task 69: 「移到這裡」 for the clicked-to-select lesson -- the same cells
  // a drag could drop on (utils/lessonDrop.ts).
  function canMoveHere(timeSlot: TimeSlot | undefined): timeSlot is TimeSlot {
    return edit !== null && edit.selected !== null && canMoveLessonTo(edit.selected, timeSlot);
  }

  // Task 93: 「放到這裡」 for a selected (not dragged) card -- every
  // teaching cell, like a drop.
  function canPlaceHere(timeSlot: TimeSlot | undefined): timeSlot is TimeSlot {
    return (
      edit !== null &&
      edit.selected === null &&
      edit.placing !== null &&
      !edit.placing.isDragging &&
      timeSlot !== undefined &&
      timeSlot.is_teaching_period
    );
  }

  // Task 85: the click-flow target's accessible name -- the slot, plus what
  // moving there would do when a candidate mark is known.
  function moveTargetLabel(timeSlot: TimeSlot, mark: CandidateMark, action: CandidateAction = "move"): string {
    const target = `${action === "place" ? "放到" : "移到"} ${formatTimeSlotLabel(timeSlot, periodDisplay)}`;
    const description = candidateDescription(mark, action);
    return description === null ? target : `${target}（${description}）`;
  }

  return (
    <div className={TABLE_WRAPPER}>
      <table className={TABLE} onDragLeave={edit !== null ? handleTableDragLeave : undefined}>
        <thead>
          <tr className={TABLE_HEAD_ROW}>
            <th className={TH}>節次</th>
            {WEEKDAYS.map((weekday) => (
              <th key={weekday} className={TH}>
                {formatWeekday(weekday)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {periods.map((period) => {
            const rowDisplay = periodDisplay.get(period);
            const isNonTeachingRow = rowDisplay?.kind === "nonTeaching";
            return (
            <tr key={period} className={TR_HOVER}>
              {/* Task 78: the row header is the teaching period number
                  ("第 5 節" for raw period 6 after 午休), or the name of a
                  non-teaching row ("早自習") -- never the raw period. */}
              <th
                scope="row"
                className={isNonTeachingRow ? TIMETABLE_ROW_HEADER_NON_TEACHING : TIMETABLE_ROW_HEADER}
              >
                {formatPeriodHeader(period, periodDisplay)}
              </th>
              {WEEKDAYS.map((weekday) => {
                const key = timeSlotKey(weekday, period);
                const timeSlot = timeSlotByWeekdayAndPeriod.get(key);
                const nonTeachingLabel = cellLabelOf(timeSlot, rowDisplay);
                // Task 68: matched by TimeSlot id, so non-teaching cells
                // (H11) can be highlighted too.
                const isHighlighted =
                  highlightedTimeSlotId !== null && timeSlot?.id === highlightedTimeSlotId;
                const isAdjusted =
                  adjustedTimeSlotId !== null && timeSlot?.id === adjustedTimeSlotId;
                const dropClass = edit !== null ? cellDropClass(key, timeSlot) : null;
                // One marker per cell: a drop hint, else the just-adjusted
                // marker, else the locate highlight.
                const markerClass =
                  dropClass ?? (isAdjusted ? TD_ADJUSTED : isHighlighted ? TD_HIGHLIGHT : null);
                // Drag events only in edit mode; the read-only grid has none.
                const dropHandlers =
                  edit !== null
                    ? {
                        onDragOver: (event: DragEvent<HTMLTableCellElement>) =>
                          handleCellDragOver(key, timeSlot, event),
                        onDrop: (event: DragEvent<HTMLTableCellElement>) =>
                          handleCellDrop(timeSlot, event),
                      }
                    : {};
                // Non-teaching cells show only their own label (or the
                // generic fallback) -- never any schedule lookup, and never
                // a move or drop target.
                if (nonTeachingLabel !== null) {
                  return (
                    <td
                      key={weekday}
                      {...dropHandlers}
                      className={markerClass !== null ? `${TD_NON_TEACHING_BASE} ${markerClass}` : TD_NON_TEACHING}
                    >
                      {nonTeachingLabel}
                    </td>
                  );
                }
                const matches = schedules.filter(
                  (schedule) =>
                    schedule.period === period &&
                    schedule.weekday === weekday &&
                    lessonTargetId(schedule, viewMode) === targetId,
                );
                const cellClass = markerClass !== null ? `${TD} ${markerClass}` : TD;
                // Task 90: the first lesson here that belongs to a block.
                const blockLink =
                  matches
                    .map((lesson) => blockLinks.get(lesson.scheduleId))
                    .find((link) => link !== undefined) ?? null;
                // Task 84: the move mark for this cell (teaching cells only --
                // non-teaching ones returned above).
                const cellMark =
                  edit !== null && edit.candidateMarks !== null && timeSlot !== undefined
                    ? (edit.candidateMarks.cells.get(timeSlot.id) ?? NO_MARK)
                    : NO_MARK;
                const canDropHere = isDragActive && canDropAt(timeSlot);
                const isDragOverCell =
                  isDragActive && dragHover?.kind === "cell" && dragHover.key === key;
                // Task 85: a cell showing another marker (drag hover,
                // 剛調整, 在課表中查看) shows that instead of the fill; its
                // corner icon stays.
                const candidateCellClass =
                  markerClass !== null
                    ? ""
                    : cellMark.status === "safe"
                      ? ` ${TD_CANDIDATE_SAFE}`
                      : cellMark.status === "conflict"
                        ? ` ${TD_CANDIDATE_CONFLICT}`
                        : cellMark.status === "blocked"
                          ? ` ${TD_CANDIDATE_BLOCKED}`
                          : "";

                if (edit !== null) {
                  // Edit mode lists EVERY lesson in the cell, so a double
                  // booking can be untangled one lesson at a time. Dropping
                  // on a lesson swaps with it; on the rest of the cell, moves.
                  return (
                    <td
                      key={weekday}
                      {...dropHandlers}
                      className={`${cellClass}${candidateCellClass} relative align-top`}
                    >
                      {blockLink !== null && <BlockBar link={blockLink} />}
                      <div className="flex min-h-12 min-w-28 flex-col gap-1">
                        {isAdjusted && (
                          <span className="text-xs font-semibold text-sky-700">剛調整</span>
                        )}
                        {matches.map((lesson) => (
                          <LessonButton
                            key={lesson.scheduleId}
                            lesson={lesson}
                            viewMode={viewMode}
                            edit={edit}
                            dragState={lessonDragState(lesson)}
                            isInSelectedGroup={selectedGroup?.has(lesson.scheduleId) === true}
                            candidateMark={swapMarkOf(lesson)}
                            onDragStart={(event) => handleLessonDragStart(lesson, event)}
                            onDragEnd={endDrag}
                            onDragOver={(event) => handleLessonDragOver(lesson, event)}
                            onDrop={(event) => handleLessonDrop(lesson, event)}
                          />
                        ))}
                        {/* Task 71 / Task 85: while dragging, the whole cell is
                            the move target (dropping on a lesson swaps
                            instead). Under a cell's lessons only a thin dashed
                            strip marks the drop area; it expands to 「移到這裡」
                            while the drag is over this cell, and an empty cell
                            shows it only then. Mouse-only, so hidden from
                            assistive tech (keyboard users have the click
                            flow's buttons below). */}
                        {canDropHere &&
                          (isDragOverCell ? (
                            cellMark.status === "blocked" ? (
                              <div aria-hidden="true" data-drop-zone="" className={DROP_ZONE_BLOCKED}>
                                {cellMark.reason}
                              </div>
                            ) : (
                              <div aria-hidden="true" data-drop-zone="" className={DROP_ZONE}>
                                {markAction === "place" ? "放到這裡" : "移到這裡"}
                              </div>
                            )
                          ) : (
                            matches.length > 0 && (
                              <div aria-hidden="true" data-drop-zone="" className={DROP_STRIP} />
                            )
                          ))}
                        {/* Task 85: the click flow's move target -- the whole
                            empty cell, or a thin strip under the lessons that
                            expands on hover / focus. Both are real buttons
                            (Tab, Enter, Space). */}
                        {canMoveHere(timeSlot) && (
                          <button
                            type="button"
                            onClick={() => edit.onMoveHere(timeSlot)}
                            disabled={edit.disabled}
                            aria-label={moveTargetLabel(timeSlot, cellMark)}
                            title={candidateDescription(cellMark, "move") ?? undefined}
                            className={matches.length === 0 ? CELL_MOVE_TARGET : MOVE_TARGET_STRIP}
                          >
                            移到這裡
                          </button>
                        )}
                        {/* Task 93: the same target for a selected card. */}
                        {canPlaceHere(timeSlot) && (
                          <button
                            type="button"
                            onClick={() => edit.onPlaceOnCell(timeSlot)}
                            disabled={edit.disabled}
                            aria-label={moveTargetLabel(timeSlot, cellMark, "place")}
                            title={candidateDescription(cellMark, "place") ?? undefined}
                            className={matches.length === 0 ? CELL_MOVE_TARGET : MOVE_TARGET_STRIP}
                          >
                            放到這裡
                          </button>
                        )}
                        {/* Task 84: added last, so nothing above it ever shifts
                            position (no lesson button is remounted mid-drag). */}
                        <CandidateIcon mark={cellMark} action={markAction} />
                      </div>
                    </td>
                  );
                }

                const schedule = matches[0];
                return (
                  <td key={weekday} className={blockLink !== null ? `${cellClass} relative` : cellClass}>
                    {blockLink !== null && <BlockBar link={blockLink} />}
                    {schedule !== undefined && (
                      <>
                        {matches.length > 1 && (
                          <span title="這個時段出現多筆排課結果，顯示第一筆">⚠️ </span>
                        )}
                        <span className="font-medium text-gray-900">{schedule.subjectName}</span>
                        <br />
                        <span className="text-gray-500">{cellDetailOf(schedule, viewMode)}</span>
                      </>
                    )}
                  </td>
                );
              })}
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
