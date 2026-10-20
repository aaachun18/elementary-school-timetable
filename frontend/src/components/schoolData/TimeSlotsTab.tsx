import { useState, type ReactElement } from "react";
import { list as listTimeSlots, updateMany as updateTimeSlots } from "../../api/timeSlots";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import type { TimeSlot, TimeSlotBulkUpdateItem } from "../../types/timeSlot";
import { formatWeekday } from "../../utils/timeSlotFormat";
import { buildTimeSlotGrid, slotKey } from "../../utils/wizard";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  CHECKBOX,
  ERROR_TEXT,
  HELP_TEXT,
  INPUT,
  LOADING_TEXT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TD_NON_TEACHING,
  TH,
} from "../../styles/ui";

interface Draft {
  label: string;
  isTeachingPeriod: boolean;
}

function draftOf(slot: TimeSlot): Draft {
  return { label: slot.label ?? "", isTeachingPeriod: slot.is_teaching_period };
}

// What changed in one cell, or null when nothing did. An emptied label is
// sent as null ("no label").
function changeOf(slot: TimeSlot, draft: Draft): TimeSlotBulkUpdateItem | null {
  const label = draft.label.trim() === "" ? null : draft.label.trim();
  const change: TimeSlotBulkUpdateItem = { id: slot.id };
  if (label !== slot.label) {
    change.label = label;
  }
  if (draft.isTeachingPeriod !== slot.is_teaching_period) {
    change.is_teaching_period = draft.isTeachingPeriod;
  }
  return Object.keys(change).length > 1 ? change : null;
}

// 學校資料 > 時段: the school's fixed week (Monday-Friday, periods 0-9 for
// 國小, 0-10 for 國中/高中), built with the school -- no adding or deleting.
// Shown as a timetable; 編輯 turns every cell into a label input and a
// 可排課 checkbox, 儲存 sends every changed cell at once.
export default function TimeSlotsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, errorMessage, reload } = useResource(() => listTimeSlots(0, 1000), []);

  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  if (data === null) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  return <TimeSlotGridEditor isAdmin={isAdmin} timeSlots={data} onSaved={reload} />;
}

function TimeSlotGridEditor({
  isAdmin,
  timeSlots,
  onSaved,
}: {
  isAdmin: boolean;
  timeSlots: readonly TimeSlot[];
  onSaved: () => void;
}): ReactElement {
  const grid = buildTimeSlotGrid(timeSlots);
  const [drafts, setDrafts] = useState<Map<number, Draft> | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEditing = drafts !== null;

  function startEditing(): void {
    setDrafts(new Map(timeSlots.map((slot) => [slot.id, draftOf(slot)])));
    setError(null);
  }

  function updateDraft(slot: TimeSlot, change: Partial<Draft>): void {
    setDrafts((previous) => {
      if (previous === null) {
        return previous;
      }
      const next = new Map(previous);
      next.set(slot.id, { ...(previous.get(slot.id) ?? draftOf(slot)), ...change });
      return next;
    });
  }

  async function handleSave(): Promise<void> {
    if (drafts === null) {
      return;
    }
    const changes = timeSlots
      .map((slot) => changeOf(slot, drafts.get(slot.id) ?? draftOf(slot)))
      .filter((change): change is TimeSlotBulkUpdateItem => change !== null);
    if (changes.length === 0) {
      setDrafts(null);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await updateTimeSlots(changes);
      setDrafts(null);
      onSaved();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div>
      <p className={HELP_TEXT}>
        每天的節次由學校類型決定（國小第 0 到 9 節、國中與高中第 0 到 10 節），不能新增或刪除；可以修改每一節的標籤與是否可排課。不可排課的時段不會被排入課程，也不能設為年級的可排節次。
      </p>
      {isAdmin && (
        <div className="mb-3 flex gap-2">
          {isEditing ? (
            <>
              <button type="button" onClick={() => void handleSave()} disabled={isSaving} className={BUTTON_PRIMARY}>
                {isSaving ? "儲存中…" : "儲存"}
              </button>
              <button type="button" onClick={() => setDrafts(null)} disabled={isSaving} className={BUTTON_SECONDARY}>
                取消
              </button>
            </>
          ) : (
            <button type="button" onClick={startEditing} className={BUTTON_PRIMARY}>
              編輯
            </button>
          )}
        </div>
      )}
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
      <div className={TABLE_WRAPPER}>
        <table className={TABLE}>
          <thead>
            <tr className={TABLE_HEAD_ROW}>
              <th className={TH}>節次</th>
              {grid.weekdays.map((weekday) => (
                <th key={weekday} className={TH}>
                  {formatWeekday(weekday)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.periods.map((period) => (
              <tr key={period}>
                <th scope="row" className={TH}>
                  第 {period} 節
                </th>
                {grid.weekdays.map((weekday) => {
                  const slot = grid.slotAt.get(slotKey(weekday, period));
                  if (slot === undefined) {
                    return <td key={weekday} className={TD} />;
                  }
                  const draft = drafts?.get(slot.id) ?? draftOf(slot);
                  const where = `${formatWeekday(weekday)}第 ${period} 節`;
                  if (isEditing) {
                    return (
                      <td key={weekday} className={TD}>
                        <div className="flex flex-col gap-1">
                          <input
                            value={draft.label}
                            onChange={(event) => updateDraft(slot, { label: event.target.value })}
                            disabled={isSaving}
                            placeholder="標籤"
                            aria-label={`${where}標籤`}
                            className={`${INPUT} w-24`}
                          />
                          <label className="flex items-center gap-1 text-xs text-gray-600">
                            <input
                              type="checkbox"
                              checked={draft.isTeachingPeriod}
                              onChange={(event) => updateDraft(slot, { isTeachingPeriod: event.target.checked })}
                              disabled={isSaving}
                              aria-label={`${where}可排課`}
                              className={CHECKBOX}
                            />
                            可排課
                          </label>
                        </div>
                      </td>
                    );
                  }
                  return (
                    <td key={weekday} className={slot.is_teaching_period ? TD : TD_NON_TEACHING}>
                      <div>{slot.label ?? ""}</div>
                      <div className="text-xs text-gray-500">{slot.is_teaching_period ? "可排課" : "不可排課"}</div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
