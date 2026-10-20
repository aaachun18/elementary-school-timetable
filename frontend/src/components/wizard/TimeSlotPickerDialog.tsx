import { useState, type ReactElement } from "react";
import ConfirmDialog from "../ConfirmDialog";
import type { TimeSlot } from "../../types/timeSlot";
import { buildPeriodDisplay, formatPeriodHeader } from "../../utils/periodDisplay";
import { formatWeekday } from "../../utils/timeSlotFormat";
import { buildTimeSlotGrid, slotKey } from "../../utils/wizard";
import { BUTTON_SECONDARY_SM, CHECKBOX, ERROR_TEXT, HELP_TEXT } from "../../styles/ui";

// Task 98: the wizard's 「用課表的方式勾選」 dialog -- a teacher's
// unavailable slots (step 6) or a grade's open slots (step 8). The school's
// time slots as a weekly grid, one checkbox per teaching period;
// non-teaching periods (午休 ...) are shown but can't be checked. Mounted
// only while open (keyed by the caller), so the checks start from
// `initialSelected` every time.
export default function TimeSlotPickerDialog({
  title,
  description,
  checkedLabel,
  timeSlots,
  initialSelected,
  busy,
  errorMessage,
  requireOne,
  onSave,
  onCancel,
}: {
  title: string;
  description: string;
  // What a checked box means, e.g. 「不可排課」 / 「可排課」.
  checkedLabel: string;
  timeSlots: readonly TimeSlot[];
  initialSelected: readonly number[];
  busy: boolean;
  errorMessage: string | null;
  // A grade must stay open for at least one slot.
  requireOne: boolean;
  onSave: (timeSlotIds: number[]) => void;
  onCancel: () => void;
}): ReactElement {
  const [selected, setSelected] = useState<Set<number>>(() => new Set(initialSelected));
  const grid = buildTimeSlotGrid([...timeSlots]);
  const periodDisplay = buildPeriodDisplay(timeSlots);
  const teachingIds = timeSlots.filter((slot) => slot.is_teaching_period).map((slot) => slot.id);

  function toggle(timeSlotId: number): void {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(timeSlotId)) {
        next.delete(timeSlotId);
      } else {
        next.add(timeSlotId);
      }
      return next;
    });
  }

  function setDay(weekday: number, checked: boolean): void {
    const dayIds = timeSlots
      .filter((slot) => slot.weekday === weekday && slot.is_teaching_period)
      .map((slot) => slot.id);
    setSelected((previous) => {
      const next = new Set(previous);
      for (const id of dayIds) {
        if (checked) {
          next.add(id);
        } else {
          next.delete(id);
        }
      }
      return next;
    });
  }

  const isEmptyRefused = requireOne && selected.size === 0;

  return (
    <ConfirmDialog
      open
      wide
      title={title}
      confirmLabel="儲存"
      busy={busy}
      busyLabel="儲存中…"
      confirmDisabled={isEmptyRefused}
      onConfirm={() => onSave([...selected].sort((a, b) => a - b))}
      onCancel={onCancel}
    >
      <p className={HELP_TEXT}>{description}</p>
      <div className="mb-2 flex flex-wrap gap-2">
        <button type="button" onClick={() => setSelected(new Set(teachingIds))} className={BUTTON_SECONDARY_SM}>
          全部勾選
        </button>
        <button type="button" onClick={() => setSelected(new Set())} className={BUTTON_SECONDARY_SM}>
          全部取消
        </button>
      </div>
      <div className="max-h-[60vh] overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="border border-gray-200 px-2 py-1 text-left">節次</th>
              {grid.weekdays.map((weekday) => {
                const dayIds = timeSlots
                  .filter((slot) => slot.weekday === weekday && slot.is_teaching_period)
                  .map((slot) => slot.id);
                const isAllChecked = dayIds.length > 0 && dayIds.every((id) => selected.has(id));
                return (
                  <th key={weekday} className="border border-gray-200 px-2 py-1">
                    <label className="inline-flex items-center gap-1">
                      <input
                        type="checkbox"
                        checked={isAllChecked}
                        onChange={(event) => setDay(weekday, event.target.checked)}
                        aria-label={`${formatWeekday(weekday)}整天`}
                        className={CHECKBOX}
                      />
                      {formatWeekday(weekday)}
                    </label>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {grid.periods.map((period) => (
              <tr key={period}>
                <th className="border border-gray-200 px-2 py-1 text-left font-normal whitespace-nowrap">
                  {formatPeriodHeader(period, periodDisplay)}
                </th>
                {grid.weekdays.map((weekday) => {
                  const slot = grid.slotAt.get(slotKey(weekday, period));
                  if (slot === undefined) {
                    return <td key={weekday} className="border border-gray-200 bg-gray-50" />;
                  }
                  if (!slot.is_teaching_period) {
                    return (
                      <td key={weekday} className="border border-gray-200 bg-gray-100 px-2 py-1 text-center text-xs text-gray-400">
                        {slot.label ?? "非教學"}
                      </td>
                    );
                  }
                  const label = `${formatWeekday(weekday)}${formatPeriodHeader(period, periodDisplay)}`;
                  return (
                    <td key={weekday} className="border border-gray-200 px-2 py-1 text-center">
                      <input
                        type="checkbox"
                        checked={selected.has(slot.id)}
                        onChange={() => toggle(slot.id)}
                        aria-label={`${label}${checkedLabel}`}
                        className={CHECKBOX}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-sm text-gray-600">
        已勾選 {selected.size} 個節次（勾選代表「{checkedLabel}」）
      </p>
      {isEmptyRefused && <p className={ERROR_TEXT}>至少要勾選一個節次。</p>}
      {errorMessage !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {errorMessage}
        </p>
      )}
    </ConfirmDialog>
  );
}
