import { useState, type FormEvent, type ReactElement } from "react";
import {
  create as createAcademicYear,
  list as listAcademicYears,
} from "../../api/academicYears";
import { create as createRecord } from "../../api/scheduleVersions";
import { create as createSemester, list as listSemesters } from "../../api/semesters";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { BUTTON_PRIMARY, CARD, ERROR_TEXT, HELP_TEXT, INPUT, LABEL, SELECT } from "../../styles/ui";
import { currentAcademicYear, currentSemesterNumber } from "../../utils/wizard";
import type { ScheduleVersion } from "../../types/scheduleVersion";

const SEMESTER_OPTIONS = [1, 2];

// Task 98, the wizard's first step: the academic year (typed, e.g. 115;
// today's by default) and the semester (1 / 2). Both are found or, if new,
// created -- then (v3) a new 尚未排課 排課紀錄 of that semester, whose
// settings the rest of the wizard fills.
export default function SemesterStep({
  initialYear,
  initialNumber,
  onChosen,
}: {
  initialYear: number | null;
  initialNumber: number | null;
  onChosen: (record: ScheduleVersion, semesterLabel: string) => void;
}): ReactElement {
  // Starts on today's 學年度 / 學期 (the arrows still move the year).
  const [yearText, setYearText] = useState(() => String(initialYear ?? currentAcademicYear(new Date())));
  const [number, setNumber] = useState(() => initialNumber ?? currentSemesterNumber(new Date()));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const year = Number(yearText);
  const isYearValid = yearText.trim() !== "" && Number.isInteger(year) && year > 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
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
      onChosen(record, `${year} 學年度第 ${number} 學期`);
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className={CARD}>
      <p className={HELP_TEXT}>
        選擇要排課的學年度與學期（預設為今天所在的學年度與學期，可以用上下鍵調整）；還沒有的學年度與學期會自動建立。按「下一步」會新增一筆「尚未排課」的排課紀錄，接下來的設定都存在這筆紀錄裡。
      </p>
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1">
          <span className={LABEL}>學年度</span>
          <input
            type="number"
            min={1}
            value={yearText}
            onChange={(event) => setYearText(event.target.value)}
            placeholder="例如：115"
            className={`${INPUT} w-32`}
            required
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className={LABEL}>學期</span>
          <select
            value={number}
            onChange={(event) => setNumber(Number(event.target.value))}
            className={SELECT}
          >
            {SEMESTER_OPTIONS.map((option) => (
              <option key={option} value={option}>
                第 {option} 學期
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!isYearValid || isSaving} className={BUTTON_PRIMARY}>
          {isSaving ? "處理中…" : "下一步"}
        </button>
      </div>
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
    </form>
  );
}
