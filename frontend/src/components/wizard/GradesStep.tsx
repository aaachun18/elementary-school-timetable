import { useState, type ReactElement } from "react";
import { list as listGrades } from "../../api/grades";
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
import { defaultOpenPeriodsText } from "../../utils/schoolStructure";
import ActionBar from "../ActionBar";
import StatusBadge from "../StatusBadge";
import CardHeader from "../CardHeader";
import TimeSlotPickerDialog from "./TimeSlotPickerDialog";
import { wizardStepLabel } from "../../utils/wizard";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  BUTTON_GHOST_SM,
  CARD,
  ERROR_TEXT,
  LOADING_TEXT,
  GRADE_ROW,
  MUTED_TEXT,
} from "../../styles/ui";

const HELP =
  "每個年級預設的可排節次列在年級旁邊；早自習、午休、放學與學校資料設為不可排課的時段一律不能勾選。";

// Task 98, wizard step 8: per grade of the school (fixed by its type:
// 國小 一到六年級, 國中 七到九年級, 高中 一到三年級 -- nothing to create
// here), the slots its classes may use in this record -- a timetable-shaped
// dialog starting from the band's default. Entering the step saves the
// default for every grade that has nothing set yet, so the counts shown are
// already the real ones.
export default function GradesStep({
  versionId,
  onBack,
  onNext,
}: {
  versionId: number;
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const grades = useResource(() => listGrades(0, 1000), []);
  const timeSlots = useResource(() => listTimeSlots(0, 1000), []);
  const saved = useResource(() => loadWithDefaults(versionId), [versionId]);

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
      key={versionId}
      versionId={versionId}
      initialGrades={grades.data}
      timeSlots={timeSlots.data}
      initialSaved={saved.data}
      onBack={onBack}
      onNext={onNext}
    />
  );
}

// The record's saved open slots, after saving each grade's default for the
// grades that have none yet (a grade whose default is empty stays unset;
// 「下一步」 then says so).
async function loadWithDefaults(versionId: number): Promise<GradeTimeSlots[]> {
  const [grades, saved] = await Promise.all([listGrades(0, 1000), listGradeTimeSlots(versionId)]);
  const savedGradeIds = new Set(saved.map((item) => item.grade_id));
  const result = [...saved];
  for (const grade of grades) {
    if (savedGradeIds.has(grade.id)) {
      continue;
    }
    const defaults = await defaultGradeTimeSlots(grade.id);
    if (defaults.length > 0) {
      result.push(await replaceGradeTimeSlots(versionId, grade.id, defaults));
    }
  }
  return result;
}

interface Picker {
  grade: Grade;
  initial: number[];
}

function GradesForm({
  versionId,
  initialGrades,
  timeSlots,
  initialSaved,
  onBack,
  onNext,
}: {
  versionId: number;
  initialGrades: readonly Grade[];
  timeSlots: readonly TimeSlot[];
  initialSaved: readonly GradeTimeSlots[];
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const grades = [...initialGrades].sort((a, b) => a.level - b.level);
  const [savedSlots, setSavedSlots] = useState<Map<number, number[]>>(
    () => new Map(initialSaved.map((item) => [item.grade_id, item.time_slot_ids])),
  );
  const [picker, setPicker] = useState<Picker | null>(null);
  const [isPickerSaving, setIsPickerSaving] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const [isFinishing, setIsFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      const result = await replaceGradeTimeSlots(versionId, picker.grade.id, timeSlotIds);
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
          setError(`${grade.name}沒有任何預設可排節次，請先到學校資料把時段設為可排課，或手動設定。`);
          return;
        }
        await replaceGradeTimeSlots(versionId, grade.id, defaults);
      }
      onNext();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsFinishing(false);
    }
  }

  return (
    <>
      <div className={CARD}>
        <CardHeader title={wizardStepLabel("grades")} info={<p>{HELP}</p>} />
        {grades.length === 0 ? (
          <p className={MUTED_TEXT}>
          學校還沒有年級。年級由學校類型決定，請聯絡系統管理員到「學校管理」確認學校設定。
        </p>
        ) : (
          <ul className="m-0 flex list-none flex-col p-0">
            {grades.map((grade) => {
              const slotIds = savedSlots.get(grade.id);
              return (
                <li key={grade.id} className={GRADE_ROW}>
                  <span className="font-medium text-gray-900">{grade.name}</span>
                  <span>
                    {slotIds === undefined ? (
                      <StatusBadge tone="neutral">尚未設定</StatusBadge>
                    ) : (
                      <StatusBadge tone="info">已開放 {slotIds.length} 個節次</StatusBadge>
                    )}
                  </span>
                  <span className={MUTED_TEXT}>
                    {slotIds === undefined ? "下一步時套用預設：" : "預設："}
                    {defaultOpenPeriodsText(grade.level)}
                  </span>
                  <button
                    type="button"
                    onClick={() => void openPicker(grade)}
                    aria-label={`設定${grade.name}的可排節次`}
                    className={`${BUTTON_GHOST_SM} justify-self-end`}
                  >
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
      <ActionBar
        start={
          <button type="button" onClick={onBack} className={BUTTON_SECONDARY}>
            上一步
          </button>
        }
        end={
          <button
            type="button"
            onClick={() => void handleNext()}
            disabled={isFinishing || grades.length === 0}
            className={BUTTON_PRIMARY}
          >
            {isFinishing ? "儲存中…" : "下一步"}
          </button>
        }
      />
    </>
  );
}
