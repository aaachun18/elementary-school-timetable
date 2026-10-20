import { useState, type ReactElement } from "react";
import { create as createGrade, list as listGrades } from "../../api/grades";
import { list as listTimeSlots } from "../../api/timeSlots";
import {
  defaultGradeTimeSlots,
  listGradeTimeSlots,
  replaceGradeTimeSlots,
} from "../../api/semesterSettings";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import type { Grade } from "../../types/grade";
import type { GradeTimeSlots } from "../../types/semesterSettings";
import type { TimeSlot } from "../../types/timeSlot";
import {
  SCHOOL_STAGE_LABELS,
  STAGE_LEVELS,
  gradeName,
  stageOfLevels,
  type SchoolStage,
} from "../../utils/wizard";
import TimeSlotPickerDialog from "./TimeSlotPickerDialog";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  BUTTON_SECONDARY_SM,
  CARD,
  CHECKBOX,
  ERROR_TEXT,
  HELP_TEXT,
  LOADING_TEXT,
  MUTED_TEXT,
  SUBSECTION_TITLE,
} from "../../styles/ui";

const DEFAULT_RULES =
  "預設：低年級星期二 0–8 節、其他天 0–5 節；中年級星期三、五 0–5 節、其他天 0–8 節；高年級星期三 0–5 節、其他天 0–8 節；國中每天 0–8 節（午休等非教學時段不排課）。";

// Task 98, wizard steps 7-8: the school's grades (國小 1-6 or 國中 7-9;
// checking a level creates that grade) and, per grade, the slots its
// classes may use this semester -- a timetable-shaped dialog starting from
// the band's default. A grade nobody opened gets its default saved on
// 「下一步」.
export default function GradesStep({
  semesterId,
  onBack,
  onNext,
}: {
  semesterId: number;
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const grades = useResource(() => listGrades(0, 1000), []);
  const timeSlots = useResource(() => listTimeSlots(0, 1000), []);
  const saved = useResource(() => listGradeTimeSlots(semesterId), [semesterId]);

  const errorMessage = grades.errorMessage ?? timeSlots.errorMessage ?? saved.errorMessage;
  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  if (grades.data === null || timeSlots.data === null || saved.data === null) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  return (
    <GradesForm
      key={semesterId}
      semesterId={semesterId}
      initialGrades={grades.data}
      timeSlots={timeSlots.data}
      initialSaved={saved.data}
      onBack={onBack}
      onNext={onNext}
    />
  );
}

interface Picker {
  grade: Grade;
  initial: number[];
}

function GradesForm({
  semesterId,
  initialGrades,
  timeSlots,
  initialSaved,
  onBack,
  onNext,
}: {
  semesterId: number;
  initialGrades: readonly Grade[];
  timeSlots: readonly TimeSlot[];
  initialSaved: readonly GradeTimeSlots[];
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const [grades, setGrades] = useState<Grade[]>(() =>
    [...initialGrades].sort((a, b) => a.level - b.level),
  );
  const [savedSlots, setSavedSlots] = useState<Map<number, number[]>>(
    () => new Map(initialSaved.map((item) => [item.grade_id, item.time_slot_ids])),
  );
  const [stage, setStage] = useState<SchoolStage>(() =>
    stageOfLevels(initialGrades.map((grade) => grade.level)),
  );
  const [creatingLevel, setCreatingLevel] = useState<number | null>(null);
  const [picker, setPicker] = useState<Picker | null>(null);
  const [isPickerSaving, setIsPickerSaving] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const [isFinishing, setIsFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const levels = new Set(grades.map((grade) => grade.level));

  async function handleCreateGrade(level: number): Promise<void> {
    setCreatingLevel(level);
    setError(null);
    try {
      const created = await createGrade({ name: gradeName(level), level });
      setGrades((previous) => [...previous, created].sort((a, b) => a.level - b.level));
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setCreatingLevel(null);
    }
  }

  async function openPicker(grade: Grade): Promise<void> {
    setError(null);
    setPickerError(null);
    try {
      const initial = savedSlots.get(grade.id) ?? (await defaultGradeTimeSlots(grade.id));
      setPicker({ grade, initial });
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    }
  }

  async function handlePickerSave(timeSlotIds: number[]): Promise<void> {
    if (picker === null) {
      return;
    }
    setIsPickerSaving(true);
    setPickerError(null);
    try {
      const result = await replaceGradeTimeSlots(semesterId, picker.grade.id, timeSlotIds);
      setSavedSlots((previous) => new Map(previous).set(result.grade_id, result.time_slot_ids));
      setPicker(null);
    } catch (caught) {
      setPickerError(extractApiErrorMessage(caught));
    } finally {
      setIsPickerSaving(false);
    }
  }

  async function handleNext(): Promise<void> {
    setIsFinishing(true);
    setError(null);
    try {
      for (const grade of grades) {
        if (savedSlots.has(grade.id)) {
          continue;
        }
        const defaults = await defaultGradeTimeSlots(grade.id);
        if (defaults.length === 0) {
          setError(`${grade.name}沒有任何預設可排節次，請先到學校資料建立時段，或手動設定。`);
          return;
        }
        await replaceGradeTimeSlots(semesterId, grade.id, defaults);
      }
      onNext();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsFinishing(false);
    }
  }

  return (
    <div className={CARD}>
      <h3 className={SUBSECTION_TITLE}>建立年級</h3>
      <div className="mb-2 flex flex-wrap gap-4 text-sm">
        {(Object.keys(SCHOOL_STAGE_LABELS) as SchoolStage[]).map((option) => (
          <label key={option} className="inline-flex items-center gap-1">
            <input
              type="radio"
              name="school-stage"
              checked={stage === option}
              onChange={() => setStage(option)}
              className="accent-blue-600"
            />
            {SCHOOL_STAGE_LABELS[option]}
          </label>
        ))}
      </div>
      <div className="mb-1 flex flex-wrap gap-3 text-sm">
        {STAGE_LEVELS[stage].map((level) => (
          <label key={level} className="inline-flex items-center gap-1">
            <input
              type="checkbox"
              checked={levels.has(level)}
              disabled={levels.has(level) || creatingLevel !== null}
              onChange={() => void handleCreateGrade(level)}
              className={CHECKBOX}
            />
            {gradeName(level)}
          </label>
        ))}
      </div>
      <p className={MUTED_TEXT}>勾選即建立該年級；要刪除年級請到學校資料。</p>

      <h3 className={`${SUBSECTION_TITLE} mt-4`}>每個年級每週可以排課的節次</h3>
      <p className={HELP_TEXT}>{DEFAULT_RULES}</p>
      {grades.length === 0 ? (
        <p className={MUTED_TEXT}>請先勾選要建立的年級。</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {grades.map((grade) => {
            const slotIds = savedSlots.get(grade.id);
            return (
              <li key={grade.id} className="flex flex-wrap items-center gap-3 text-sm">
                <span className="w-20 font-medium text-gray-900">{grade.name}</span>
                <span className="text-gray-700">
                  {slotIds === undefined ? "尚未設定（下一步時套用預設）" : `已開放 ${slotIds.length} 個節次`}
                </span>
                <button type="button" onClick={() => void openPicker(grade)} className={BUTTON_SECONDARY_SM}>
                  設定可排節次
                </button>
              </li>
            );
          })}
        </ul>
      )}
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
          onClick={() => void handleNext()}
          disabled={isFinishing || grades.length === 0}
          className={BUTTON_PRIMARY}
        >
          {isFinishing ? "儲存中…" : "下一步"}
        </button>
      </div>
      {picker !== null && (
        <TimeSlotPickerDialog
          key={picker.grade.id}
          title={`${picker.grade.name}的可排節次`}
          description="勾選這學期這個年級可以排課的節次；沒勾的節次不會排課。"
          checkedLabel="可排課"
          timeSlots={timeSlots}
          initialSelected={picker.initial}
          busy={isPickerSaving}
          errorMessage={pickerError}
          requireOne
          onSave={(ids) => void handlePickerSave(ids)}
          onCancel={() => setPicker(null)}
        />
      )}
    </div>
  );
}
