import { useState, type ReactElement } from "react";
import {
  create as createRequirement,
  list as listRequirements,
  remove as removeRequirement,
  update as updateRequirement,
} from "../../api/gradeSubjectRequirements";
import { list as listGrades } from "../../api/grades";
import { list as listSubjects } from "../../api/subjects";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import type { Grade } from "../../types/grade";
import type { GradeSubjectRequirement } from "../../types/gradeSubjectRequirement";
import type { Subject } from "../../types/subject";
import { WEEKLY_PERIOD_OPTIONS } from "../../utils/wizard";
import {
  BUTTON_DANGER_SM,
  BUTTON_PRIMARY,
  ERROR_TEXT,
  HELP_TEXT,
  LABEL,
  LOADING_TEXT,
  SELECT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TH,
  TR_HOVER,
} from "../../styles/ui";

const DEFAULT_WEEKLY_PERIODS = 1;

// 學校資料 > 科目需求: how many periods a week every class of a grade
// needs of each subject (1-6). 開始排課's 科目需求 step copies these into
// the semester; there only the lesson pattern, teacher and room are set.
export default function GradeRequirementsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const grades = useResource(() => listGrades(0, 1000), []);
  const subjects = useResource(() => listSubjects(0, 1000), []);
  const requirements = useResource(() => listRequirements(), []);

  const errorMessage = grades.errorMessage ?? subjects.errorMessage ?? requirements.errorMessage;
  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  if (grades.data === null || subjects.data === null || requirements.data === null) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  const sortedGrades = [...grades.data].sort((a, b) => a.level - b.level);
  if (sortedGrades.length === 0) {
    return <p className={HELP_TEXT}>學校還沒有年級。</p>;
  }
  return (
    <GradeRequirementsEditor
      isAdmin={isAdmin}
      grades={sortedGrades}
      subjects={subjects.data}
      requirements={requirements.data}
      onChanged={requirements.reload}
    />
  );
}

function GradeRequirementsEditor({
  isAdmin,
  grades,
  subjects,
  requirements,
  onChanged,
}: {
  isAdmin: boolean;
  grades: readonly Grade[];
  subjects: readonly Subject[];
  requirements: readonly GradeSubjectRequirement[];
  onChanged: () => void;
}): ReactElement {
  const [gradeId, setGradeId] = useState<number>(grades[0].id);
  const [newSubjectId, setNewSubjectId] = useState<number | null>(null);
  const [newWeeklyPeriods, setNewWeeklyPeriods] = useState(DEFAULT_WEEKLY_PERIODS);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const subjectName = new Map(subjects.map((subject) => [subject.id, subject.name]));
  const gradeRequirements = requirements.filter((requirement) => requirement.grade_id === gradeId);
  const usedSubjectIds = new Set(gradeRequirements.map((requirement) => requirement.subject_id));
  const addableSubjects = subjects.filter((subject) => subject.is_active && !usedSubjectIds.has(subject.id));

  async function run(action: () => Promise<unknown>): Promise<boolean> {
    setIsPending(true);
    setError(null);
    try {
      await action();
      onChanged();
      return true;
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
      return false;
    } finally {
      setIsPending(false);
    }
  }

  async function handleAdd(): Promise<void> {
    if (newSubjectId === null) {
      return;
    }
    const added = await run(() =>
      createRequirement({ grade_id: gradeId, subject_id: newSubjectId, weekly_periods: newWeeklyPeriods }),
    );
    if (added) {
      setNewSubjectId(null);
      setNewWeeklyPeriods(DEFAULT_WEEKLY_PERIODS);
    }
  }

  function handleDelete(requirement: GradeSubjectRequirement): void {
    const name = subjectName.get(requirement.subject_id) ?? "這個科目";
    if (window.confirm(`確定要刪除「${name}」的科目需求嗎？`)) {
      void run(() => removeRequirement(requirement.id));
    }
  }

  return (
    <div>
      <p className={HELP_TEXT}>
        設定每個年級各科目每週需要的節數，同年級的每個班級都適用。開始排課的「科目需求」步驟會自動帶入這裡的設定。
      </p>
      <label className="mb-3 flex flex-col gap-1">
        <span className={LABEL}>年級</span>
        <select
          value={gradeId}
          onChange={(event) => {
            setGradeId(Number(event.target.value));
            setNewSubjectId(null);
          }}
          aria-label="年級"
          className={`${SELECT} w-40`}
        >
          {grades.map((grade) => (
            <option key={grade.id} value={grade.id}>
              {grade.name}
            </option>
          ))}
        </select>
      </label>
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
      <div className={TABLE_WRAPPER}>
        <table className={TABLE}>
          <thead>
            <tr className={TABLE_HEAD_ROW}>
              <th className={TH}>科目</th>
              <th className={TH}>每週節數</th>
              {isAdmin && <th className={TH}>操作</th>}
            </tr>
          </thead>
          <tbody>
            {gradeRequirements.map((requirement) => (
              <tr key={requirement.id} className={TR_HOVER}>
                <td className={TD}>{subjectName.get(requirement.subject_id) ?? "—"}</td>
                <td className={TD}>
                  {isAdmin ? (
                    <select
                      value={requirement.weekly_periods}
                      onChange={(event) =>
                        void run(() =>
                          updateRequirement(requirement.id, { weekly_periods: Number(event.target.value) }),
                        )
                      }
                      disabled={isPending}
                      aria-label={`${subjectName.get(requirement.subject_id) ?? ""}每週節數`}
                      className={`${SELECT} w-24`}
                    >
                      {WEEKLY_PERIOD_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option} 節
                        </option>
                      ))}
                    </select>
                  ) : (
                    `${requirement.weekly_periods} 節`
                  )}
                </td>
                {isAdmin && (
                  <td className={TD}>
                    <button
                      type="button"
                      onClick={() => handleDelete(requirement)}
                      disabled={isPending}
                      className={BUTTON_DANGER_SM}
                    >
                      刪除
                    </button>
                  </td>
                )}
              </tr>
            ))}
            {gradeRequirements.length === 0 && (
              <tr>
                <td className={TD} colSpan={isAdmin ? 3 : 2}>
                  <span className={HELP_TEXT}>這個年級還沒有科目需求。</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {isAdmin && (
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className={LABEL}>科目</span>
            <select
              value={newSubjectId ?? ""}
              onChange={(event) => setNewSubjectId(event.target.value === "" ? null : Number(event.target.value))}
              disabled={isPending}
              aria-label="新增科目"
              className={`${SELECT} w-40`}
            >
              <option value="">請選擇科目</option>
              {addableSubjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className={LABEL}>每週節數</span>
            <select
              value={newWeeklyPeriods}
              onChange={(event) => setNewWeeklyPeriods(Number(event.target.value))}
              disabled={isPending}
              aria-label="新增每週節數"
              className={`${SELECT} w-24`}
            >
              {WEEKLY_PERIOD_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option} 節
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => void handleAdd()}
            disabled={isPending || newSubjectId === null}
            className={BUTTON_PRIMARY}
          >
            新增科目需求
          </button>
        </div>
      )}
    </div>
  );
}
