import type { ReactElement } from "react";
import { timeSlotKey, type EnrichedSchedule } from "../hooks/useTimetableData";
import { formatTimeSlotLabel, formatWeekday } from "../utils/timeSlotFormat";
import type { TimetableViewMode } from "../utils/violationLocate";
import type { Lesson } from "../types/lesson";
import type { TimeSlot } from "../types/timeSlot";
import {
  BADGE_NEUTRAL,
  LESSON_BUTTON,
  LESSON_BUTTON_SELECTED,
  MOVE_TARGET_BUTTON,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TD_HIGHLIGHT,
  TH,
} from "../styles/ui";

const WEEKDAYS = [1, 2, 3, 4, 5];

// Task 69: present only in edit mode. Without it the grid renders exactly
// as the read-only timetable always has.
export interface TimetableGridEditProps {
  selected: EnrichedSchedule | null;
  // A preview/save request is in flight: nothing can be clicked.
  disabled: boolean;
  // For the 「固定」 marker (Lesson.fixed_time_slot_id).
  lessonById: Map<number, Lesson>;
  onLessonClick: (lesson: EnrichedSchedule) => void;
  onMoveHere: (timeSlot: TimeSlot) => void;
}

interface TimetableGridProps {
  periods: number[];
  schedules: EnrichedSchedule[];
  viewMode: TimetableViewMode;
  targetId: number;
  timeSlotByWeekdayAndPeriod: Map<string, TimeSlot>;
  highlightedTimeSlotId: number | null;
  edit: TimetableGridEditProps | null;
}

function targetIdOf(row: EnrichedSchedule, viewMode: TimetableViewMode): number | null {
  if (viewMode === "class") {
    return row.classId;
  }
  if (viewMode === "teacher") {
    return row.teacherId;
  }
  return row.roomId;
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

// Task 69: one lesson as a button (edit mode only).
function LessonButton({
  lesson,
  viewMode,
  edit,
}: {
  lesson: EnrichedSchedule;
  viewMode: TimetableViewMode;
  edit: TimetableGridEditProps;
}): ReactElement {
  const isSelected = edit.selected?.scheduleId === lesson.scheduleId;
  const isFixed = (edit.lessonById.get(lesson.lessonId)?.fixed_time_slot_id ?? null) !== null;
  return (
    <button
      type="button"
      onClick={() => edit.onLessonClick(lesson)}
      disabled={edit.disabled}
      aria-pressed={isSelected}
      aria-label={lessonAriaLabel(lesson, edit.selected)}
      className={isSelected ? LESSON_BUTTON_SELECTED : LESSON_BUTTON}
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
  schedules,
  viewMode,
  targetId,
  timeSlotByWeekdayAndPeriod,
  highlightedTimeSlotId,
  edit,
}: TimetableGridProps): ReactElement {
  // Task 35.5: teaching/non-teaching status and label are decided per
  // CELL (this exact weekday+period's own TimeSlot), not per row -- the
  // same period can be "早自習" on Monday and "導師時間" on Wednesday, and
  // each cell must show its own name rather than one collapsed row title.
  // A missing TimeSlot record for this exact weekday+period is treated as
  // an ordinary teaching slot, matching TimeSlotBase's own
  // is_teaching_period default of True.
  function cellLabelOf(timeSlot: TimeSlot | undefined): string | null {
    if (timeSlot === undefined || timeSlot.is_teaching_period) {
      return null;
    }
    return timeSlot.label ?? "非教學時段";
  }

  // Task 69: 「移到這裡」 only on a real teaching TimeSlot other than the
  // selected lesson's current one (a cell with no TimeSlot record has no id
  // to move to).
  function canMoveHere(timeSlot: TimeSlot | undefined): timeSlot is TimeSlot {
    return (
      edit !== null &&
      edit.selected !== null &&
      timeSlot !== undefined &&
      timeSlot.is_teaching_period &&
      timeSlot.id !== edit.selected.timeSlotId
    );
  }

  return (
    <div className={TABLE_WRAPPER}>
      <table className={TABLE}>
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
          {periods.map((period) => (
            <tr key={period} className="hover:bg-gray-50">
              {/* Task 35.5: the row header is a plain, weekday-independent
                  period number -- a single period can have different
                  labels on different weekdays. */}
              <th scope="row" className={`${TH} bg-white font-medium text-gray-600`}>
                第 {period} 節
              </th>
              {WEEKDAYS.map((weekday) => {
                const timeSlot = timeSlotByWeekdayAndPeriod.get(timeSlotKey(weekday, period));
                const nonTeachingLabel = cellLabelOf(timeSlot);
                // Task 68: matched by TimeSlot id, so non-teaching cells
                // (H11) can be highlighted too.
                const isHighlighted =
                  highlightedTimeSlotId !== null && timeSlot?.id === highlightedTimeSlotId;
                // Non-teaching cells show only their own label (or the
                // generic fallback) -- never any schedule lookup, and never
                // a move target.
                if (nonTeachingLabel !== null) {
                  return (
                    <td
                      key={weekday}
                      className={`${TD} text-gray-400 ${isHighlighted ? TD_HIGHLIGHT : "bg-gray-50"}`}
                    >
                      {nonTeachingLabel}
                    </td>
                  );
                }
                const matches = schedules.filter(
                  (schedule) =>
                    schedule.period === period &&
                    schedule.weekday === weekday &&
                    targetIdOf(schedule, viewMode) === targetId,
                );
                const cellClass = isHighlighted ? `${TD} ${TD_HIGHLIGHT}` : TD;

                if (edit !== null) {
                  // Edit mode lists EVERY lesson in the cell, so a double
                  // booking can be untangled one lesson at a time.
                  return (
                    <td key={weekday} className={`${cellClass} align-top`}>
                      <div className="flex min-w-28 flex-col gap-1">
                        {matches.map((lesson) => (
                          <LessonButton
                            key={lesson.scheduleId}
                            lesson={lesson}
                            viewMode={viewMode}
                            edit={edit}
                          />
                        ))}
                        {canMoveHere(timeSlot) && (
                          <button
                            type="button"
                            onClick={() => edit.onMoveHere(timeSlot)}
                            disabled={edit.disabled}
                            aria-label={`移到 ${formatTimeSlotLabel(timeSlot)}`}
                            className={MOVE_TARGET_BUTTON}
                          >
                            移到這裡
                          </button>
                        )}
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
          ))}
        </tbody>
      </table>
    </div>
  );
}
