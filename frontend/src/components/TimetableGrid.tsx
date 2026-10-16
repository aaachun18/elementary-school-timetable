import { useState, type DragEvent, type ReactElement } from "react";
import { timeSlotKey, type EnrichedSchedule } from "../hooks/useTimetableData";
import { canMoveLessonTo, canSwapLessons, lessonTargetId } from "../utils/lessonDrop";
import {
  NO_MARK,
  candidateDescription,
  candidateLabel,
  swapMarkKey,
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
  CANDIDATE_ICON_CONFLICT,
  CANDIDATE_ICON_SAFE,
  CELL_MOVE_TARGET,
  DROP_TARGET_BLOCKED,
  DROP_TARGET_OK,
  DROP_STRIP,
  DROP_ZONE,
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
function CandidateIcon({ mark }: { mark: CandidateMark }): ReactElement | null {
  const label = candidateLabel(mark, "move");
  const description = candidateDescription(mark, "move");
  if (label === null || description === null) {
    return null;
  }
  const isSafe = mark.status === "safe";
  return (
    <span
      className={isSafe ? CANDIDATE_ICON_SAFE : CANDIDATE_ICON_CONFLICT}
      title={`${label}：${description}`}
      aria-label={`${label}：${description}`}
      role="img"
    >
      {isSafe ? "✓" : "✕"}
    </span>
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
  const name = `${lesson.className} ${lesson.subjectName}`;
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
      : isSelected
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
    endDrag();
    if (edit !== null && !edit.disabled && lesson !== undefined && canSwapLessons(lesson, target)) {
      edit.onDropOnLesson(lesson, target);
    }
  }

  function handleCellDragOver(
    key: string,
    timeSlot: TimeSlot | undefined,
    event: DragEvent<HTMLTableCellElement>,
  ): void {
    if (dragging === null) {
      return;
    }
    updateHover({ kind: "cell", key });
    if (canMoveLessonTo(dragging, timeSlot)) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    } else {
      event.dataTransfer.dropEffect = "none";
    }
  }

  function handleCellDrop(timeSlot: TimeSlot | undefined, event: DragEvent<HTMLTableCellElement>): void {
    event.preventDefault();
    const lesson = draggedLessonOf(event);
    endDrag();
    if (edit !== null && !edit.disabled && lesson !== undefined && canMoveLessonTo(lesson, timeSlot)) {
      edit.onDropOnCell(lesson, timeSlot);
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
    if (dragging === null || dragHover?.kind !== "cell" || dragHover.key !== key) {
      return null;
    }
    return canMoveLessonTo(dragging, timeSlot) ? DROP_TARGET_OK : DROP_TARGET_BLOCKED;
  }

  function lessonDragState(lesson: EnrichedSchedule): LessonDragState {
    if (dragging === null) {
      return null;
    }
    if (dragging.scheduleId === lesson.scheduleId) {
      return "dragging";
    }
    if (dragHover?.kind === "lesson" && dragHover.scheduleId === lesson.scheduleId) {
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

  // Task 85: the click-flow target's accessible name -- the slot, plus what
  // moving there would do when a candidate mark is known.
  function moveTargetLabel(timeSlot: TimeSlot, mark: CandidateMark): string {
    const target = `移到 ${formatTimeSlotLabel(timeSlot, periodDisplay)}`;
    const description = candidateDescription(mark, "move");
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
                // Task 84: the move mark for this cell (teaching cells only --
                // non-teaching ones returned above).
                const cellMark =
                  edit !== null && edit.candidateMarks !== null && timeSlot !== undefined
                    ? (edit.candidateMarks.cells.get(timeSlot.id) ?? NO_MARK)
                    : NO_MARK;
                const canDropHere = dragging !== null && canMoveLessonTo(dragging, timeSlot);
                const isDragOverCell =
                  dragging !== null && dragHover?.kind === "cell" && dragHover.key === key;
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
                            candidateMark={
                              edit.candidateMarks !== null && timeSlot !== undefined
                                ? (edit.candidateMarks.swaps.get(
                                    swapMarkKey(timeSlot.id, lesson.scheduleId),
                                  ) ?? NO_MARK)
                                : NO_MARK
                            }
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
                            <div aria-hidden="true" data-drop-zone="" className={DROP_ZONE}>
                              移到這裡
                            </div>
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
                        {/* Task 84: added last, so nothing above it ever shifts
                            position (no lesson button is remounted mid-drag). */}
                        <CandidateIcon mark={cellMark} />
                      </div>
                    </td>
                  );
                }

                const schedule = matches[0];
                return (
                  <td key={weekday} className={cellClass}>
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
