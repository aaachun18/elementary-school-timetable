import { useState, type FormEvent, type ReactElement } from "react";
import {
  create as createAcademicYear,
  list as listAcademicYears,
} from "../../api/academicYears";
import { create as createSemester, list as listSemesters } from "../../api/semesters";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { BUTTON_PRIMARY, CARD, ERROR_TEXT, HELP_TEXT, INPUT, LABEL, SELECT } from "../../styles/ui";

const SEMESTER_OPTIONS = [1, 2];

// Task 98, wizard steps 2-3: the academic year (typed, e.g. 115) and the
// semester (1 / 2). Both are found or, if new, created -- the rest of the
// wizard works on that semester.
export default function SemesterStep({
  initialYear,
  initialNumber,
  onChosen,
}: {
  initialYear: number | null;
  initialNumber: number | null;
  onChosen: (semesterId: number, label: string) => void;
}): ReactElement {
  const [yearText, setYearText] = useState(initialYear === null ? "" : String(initialYear));
  const [number, setNumber] = useState(initialNumber ?? 1);
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
      onChosen(semester.id, `${year} 學年度第 ${number} 學期`);
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className={CARD}>
      <p className={HELP_TEXT}>輸入要排課的學年度並選擇學期；還沒有的學年度與學期會自動建立。</p>
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
