import { useState, type FormEvent, type ReactElement } from "react";
import {
  create as createAcademicYear,
  list as listAcademicYears,
} from "../../api/academicYears";
import { create as createRecord } from "../../api/scheduleVersions";
import { create as createSemester, list as listSemesters } from "../../api/semesters";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { BUTTON_PRIMARY, BUTTON_SECONDARY_SM, CARD, ERROR_TEXT, INPUT, LABEL, SELECT } from "../../styles/ui";
import ActionBar from "../ActionBar";
import CardHeader from "../CardHeader";
import { currentAcademicYear, currentSemesterNumber, wizardStepLabel } from "../../utils/wizard";
import type { ScheduleVersion } from "../../types/scheduleVersion";

const SEMESTER_OPTIONS = [1, 2];

// Task 98, the wizard's first step: the academic year (typed, e.g. 115;
// today's by default) and the semester (1 / 2). Both are found or, if new,
// created -- then (v3) a new 尚未排課 排課紀錄 of that semester, whose
// settings the rest of the wizard fills.
// Task 100 (item 8): once that record exists (`locked`, see
// isSemesterStepLocked()), the fields show its semester read-only, with
// why and a 「另開新的排課」 (the header's own handler); 下一步 then only
// moves on, it never creates another record.
export interface LockedSemester {
  year: number | null;
  number: number | null;
  onStartNew: () => void;
  onNext: () => void;
}

export default function SemesterStep({
  initialYear,
  initialNumber,
  onChosen,
  locked = null,
}: {
  initialYear: number | null;
  initialNumber: number | null;
  onChosen: (record: ScheduleVersion, semester: { label: string; year: number; number: number }) => void;
  locked?: LockedSemester | null;
}): ReactElement {
  // Starts on today's 學年度 / 學期 (the arrows still move the year).
  const [yearText, setYearText] = useState(() =>
    String(locked?.year ?? initialYear ?? currentAcademicYear(new Date())),
  );
  const [number, setNumber] = useState(() => locked?.number ?? initialNumber ?? currentSemesterNumber(new Date()));
  const isLocked = locked !== null;
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const year = Number(yearText);
  const isYearValid = yearText.trim() !== "" && Number.isInteger(year) && year > 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (locked !== null) {
      locked.onNext();
      return;
    }
    if (!isYearValid) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const academicYear =
        (await listAcademicYears(0, 1000)).find((item) => item.year === year) ??
        (await createAcademicYear({ year }));
      const semester =
        (await listSemesters(0, 1000)).find(
          (item) => item.academic_year_id === academicYear.id && item.number === number,
        ) ?? (await createSemester({ academic_year_id: academicYear.id, number }));
      const record = await createRecord({ semester_id: semester.id });
      onChosen(record, { label: `${year} 學年度第 ${number} 學期`, year, number });
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <div className={CARD}>
        <CardHeader
          title={wizardStepLabel("semester")}
          info={
            <p>
              {isLocked
                ? "排課紀錄是某個學期設定的快照，建立後學期就固定了；按「下一步」回到教師設定，不會新增紀錄。"
                : "選擇要排課的學年度與學期（預設為今天所在的學年度與學期，可以用上下鍵調整）；還沒有的學年度與學期會自動建立。按「下一步」會新增一筆「尚未排課」的排課紀錄，接下來的設定都存在這筆紀錄裡。"}
            </p>
          }
        />
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1">
            <span className={LABEL}>學年度</span>
            <input
              type="number"
              min={1}
              value={yearText}
              onChange={(event) => setYearText(event.target.value)}
              placeholder="例如：115"
              disabled={isLocked}
              className={`${INPUT} w-32`}
              required
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className={LABEL}>學期</span>
            <select
              value={number}
              onChange={(event) => setNumber(Number(event.target.value))}
              disabled={isLocked}
              className={`${SELECT} w-32`}
            >
              {SEMESTER_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  第 {option} 學期
                </option>
              ))}
            </select>
          </label>
        </div>
        {locked !== null && (
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
            <p className="text-sm text-text-muted">這筆紀錄的學期已確定，無法修改。要排其他學期，請另開新的排課。</p>
            <button type="button" onClick={locked.onStartNew} className={BUTTON_SECONDARY_SM}>
              另開新的排課
            </button>
          </div>
        )}
        {error !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {error}
          </p>
        )}
      </div>
      <ActionBar
        end={
          <button type="submit" disabled={(!isLocked && !isYearValid) || isSaving} className={BUTTON_PRIMARY}>
            {isSaving ? "處理中…" : "下一步"}
          </button>
        }
      />
    </form>
  );
}
