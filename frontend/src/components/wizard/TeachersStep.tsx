import { useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { list as listTeachers } from "../../api/teachers";
import { list as listTimeSlots } from "../../api/timeSlots";
import { listTeachers as listSemesterTeachers, replaceTeachers } from "../../api/semesterSettings";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import type { SemesterTeacher, SemesterTeacherEntry } from "../../types/semesterSettings";
import type { Teacher } from "../../types/teacher";
import type { TimeSlot } from "../../types/timeSlot";
import { DEFAULT_MAX_WEEKLY_PERIODS, periodsRangeError } from "../../utils/wizard";
import TimeSlotPickerDialog from "./TimeSlotPickerDialog";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  BUTTON_SECONDARY_SM,
  CARD,
  CHECKBOX,
  ERROR_TEXT,
  HELP_TEXT,
  INPUT,
  LOADING_TEXT,
  MUTED_TEXT,
} from "../../styles/ui";

interface Draft {
  checked: boolean;
  minText: string;
  maxText: string;
  unavailable: number[];
}

function initialDrafts(teachers: readonly Teacher[], current: readonly SemesterTeacher[]): Map<number, Draft> {
  const byTeacher = new Map(current.map((item) => [item.teacher_id, item]));
  return new Map(
    teachers.map((teacher) => {
      const saved = byTeacher.get(teacher.id);
      return [
        teacher.id,
        {
          checked: saved !== undefined,
          minText: String(saved?.min_weekly_periods ?? 0),
          maxText: String(saved?.max_weekly_periods ?? DEFAULT_MAX_WEEKLY_PERIODS),
          unavailable: saved?.unavailable_time_slot_ids ?? [],
        },
      ];
    }),
  );
}

// Task 98, wizard steps 4-6: which 啟用 teacher accounts take part in this
// semester (a grid of checkboxes), each one's weekly minimum / maximum, and
// the slots they can't teach (a timetable-shaped dialog). Saved together
// with 「儲存並下一步」 (PUT /semesters/{id}/teachers, the complete list).
export default function TeachersStep({
  semesterId,
  onBack,
  onNext,
}: {
  semesterId: number;
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const teachers = useResource(() => listTeachers(0, 1000), []);
  const current = useResource(() => listSemesterTeachers(semesterId), [semesterId]);
  const timeSlots = useResource(() => listTimeSlots(0, 1000), []);

  const errorMessage = teachers.errorMessage ?? current.errorMessage ?? timeSlots.errorMessage;
  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  if (teachers.data === null || current.data === null || timeSlots.data === null) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  return (
    <TeachersForm
      key={semesterId}
      semesterId={semesterId}
      teachers={teachers.data.filter((teacher) => teacher.is_active)}
      current={current.data}
      timeSlots={timeSlots.data}
      onBack={onBack}
      onNext={onNext}
    />
  );
}

function TeachersForm({
  semesterId,
  teachers,
  current,
  timeSlots,
  onBack,
  onNext,
}: {
  semesterId: number;
  teachers: readonly Teacher[];
  current: readonly SemesterTeacher[];
  timeSlots: readonly TimeSlot[];
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const [drafts, setDrafts] = useState(() => initialDrafts(teachers, current));
  const [pickerTeacher, setPickerTeacher] = useState<Teacher | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update(teacherId: number, change: Partial<Draft>): void {
    setDrafts((previous) => {
      const next = new Map(previous);
      const draft = next.get(teacherId);
      if (draft !== undefined) {
        next.set(teacherId, { ...draft, ...change });
      }
      return next;
    });
  }

  const checkedTeachers = teachers.filter((teacher) => drafts.get(teacher.id)?.checked === true);
  const rangeErrors = new Map(
    checkedTeachers.map((teacher) => {
      const draft = drafts.get(teacher.id) as Draft;
      return [teacher.id, periodsRangeError(draft.minText, draft.maxText)];
    }),
  );
  const hasRangeError = [...rangeErrors.values()].some((message) => message !== null);

  async function handleSave(): Promise<void> {
    setIsSaving(true);
    setError(null);
    const entries: SemesterTeacherEntry[] = checkedTeachers.map((teacher) => {
      const draft = drafts.get(teacher.id) as Draft;
      return {
        teacher_id: teacher.id,
        min_weekly_periods: Number(draft.minText),
        max_weekly_periods: Number(draft.maxText),
        unavailable_time_slot_ids: draft.unavailable,
      };
    });
    try {
      await replaceTeachers(semesterId, entries);
      onNext();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className={CARD}>
      <p className={HELP_TEXT}>
        勾選要納入這次排課的老師，設定每週最低與最高節數，並標出沒辦法排課的時間。沒有指定老師的課程，會分給還沒超過上限的老師。
        名單是所有啟用中的一般老師帳號，要新增老師請到
        <Link to="/users" className="font-medium text-blue-600 hover:underline">
          帳號管理
        </Link>
        。
      </p>
      {teachers.length === 0 ? (
        <p className={MUTED_TEXT}>目前沒有啟用中的老師帳號。</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {teachers.map((teacher) => {
            const draft = drafts.get(teacher.id) as Draft;
            const rangeError = rangeErrors.get(teacher.id) ?? null;
            return (
              <div key={teacher.id} className="rounded border border-gray-200 p-3">
                <label className="flex items-center gap-2 font-medium text-gray-900">
                  <input
                    type="checkbox"
                    checked={draft.checked}
                    onChange={(event) => update(teacher.id, { checked: event.target.checked })}
                    className={CHECKBOX}
                  />
                  {teacher.name}
                </label>
                {draft.checked && (
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                    <label className="inline-flex items-center gap-1">
                      每週最低
                      <input
                        type="number"
                        min={0}
                        value={draft.minText}
                        onChange={(event) => update(teacher.id, { minText: event.target.value })}
                        aria-label={`${teacher.name}每週最低節數`}
                        className={`${INPUT} w-16`}
                      />
                    </label>
                    <label className="inline-flex items-center gap-1">
                      最高
                      <input
                        type="number"
                        min={0}
                        value={draft.maxText}
                        onChange={(event) => update(teacher.id, { maxText: event.target.value })}
                        aria-label={`${teacher.name}每週最高節數`}
                        className={`${INPUT} w-16`}
                      />
                      節
                    </label>
                    <button
                      type="button"
                      onClick={() => setPickerTeacher(teacher)}
                      className={BUTTON_SECONDARY_SM}
                    >
                      不可排時段（{draft.unavailable.length}）
                    </button>
                    {rangeError !== null && <p className={`${ERROR_TEXT} w-full`}>{rangeError}</p>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-3 text-sm text-gray-700">已納入 {checkedTeachers.length} 位老師。</p>
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
      <div className="mt-4 flex gap-2">
        <button type="button" onClick={onBack} className={BUTTON_SECONDARY}>
          上一步
        </button>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={isSaving || hasRangeError || checkedTeachers.length === 0}
          className={BUTTON_PRIMARY}
        >
          {isSaving ? "儲存中…" : "儲存並下一步"}
        </button>
      </div>
      {pickerTeacher !== null && (
        <TimeSlotPickerDialog
          key={pickerTeacher.id}
          title={`${pickerTeacher.name}的不可排課時段`}
          description="勾選這學期沒辦法排課的節次，排課時會避開。"
          checkedLabel="不可排課"
          timeSlots={timeSlots}
          initialSelected={drafts.get(pickerTeacher.id)?.unavailable ?? []}
          busy={false}
          errorMessage={null}
          requireOne={false}
          onSave={(ids) => {
            update(pickerTeacher.id, { unavailable: ids });
            setPickerTeacher(null);
          }}
          onCancel={() => setPickerTeacher(null)}
        />
      )}
    </div>
  );
}
