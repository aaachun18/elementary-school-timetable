import { useState, type ReactElement } from "react";
import {
  create as createRequirement,
  list as listRequirements,
  remove as removeRequirement,
  update as updateRequirement,
} from "../../api/gradeSubjectRequirements";
import { list as listGrades } from "../../api/grades";
import { create as createSubject, list as listSubjects } from "../../api/subjects";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useConfirm } from "../../hooks/useConfirm";
import { useResource } from "../../hooks/useResource";
import type { Grade } from "../../types/grade";
import type { GradeSubjectRequirement } from "../../types/gradeSubjectRequirement";
import type { Subject } from "../../types/subject";
import { findSubjectByName, normalizeSubjectName } from "../../utils/subjectName";
import { WEEKLY_PERIOD_OPTIONS } from "../../utils/wizard";
import { deleteButtonLabel, deleteConfirmText } from "../../utils/confirmText";
import ConfirmDialog from "../ConfirmDialog";
import DeleteIconButton from "../DeleteIconButton";
import SuggestionInput from "../SuggestionInput";
import {
  BUTTON_PRIMARY,
  ERROR_TEXT,
  FIELD_PAGE,
  HELP_TEXT,
  LABEL,
  LOADING_TEXT,
  ROW_ACTIONS_END,
  SELECT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TD_ACTIONS,
  TH,
  TH_ACTIONS,
  TR_HOVER,
} from "../../styles/ui";

const DEFAULT_WEEKLY_PERIODS = 1;

// 學校資料 > 科目需求: how many periods a week every class of a grade
// needs of each subject (1-6). 開始排課's 科目需求 step copies these into
// the semester; there only the lesson pattern, teacher and room are set.
// 「新增科目需求」 opens a dialog where the subject's name is typed freely:
// a name the school doesn't have yet also creates that subject.
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
      onSubjectsChanged={subjects.reload}
    />
  );
}

function GradeRequirementsEditor({
  isAdmin,
  grades,
  subjects,
  requirements,
  onChanged,
  onSubjectsChanged,
}: {
  isAdmin: boolean;
  grades: readonly Grade[];
  subjects: readonly Subject[];
  requirements: readonly GradeSubjectRequirement[];
  onChanged: () => void;
  onSubjectsChanged: () => void;
}): ReactElement {
  const [gradeId, setGradeId] = useState<number>(grades[0].id);
  const [isAdding, setIsAdding] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { confirm, dialog: confirmDialog } = useConfirm();

  const subjectName = new Map(subjects.map((subject) => [subject.id, subject.name]));
  const gradeRequirements = requirements.filter((requirement) => requirement.grade_id === gradeId);
  const usedSubjectIds = new Set(gradeRequirements.map((requirement) => requirement.subject_id));
  const gradeName = grades.find((grade) => grade.id === gradeId)?.name ?? "";
  // 「一年級的國語」: the requirement's name in its trash button and dialog.
  const requirementName = (requirement: GradeSubjectRequirement): string =>
    `${gradeName}的${subjectName.get(requirement.subject_id) ?? "這個科目"}`;

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

  async function handleDelete(requirement: GradeSubjectRequirement): Promise<void> {
    const confirmed = await confirm(deleteConfirmText("gradeRequirement", requirementName(requirement)));
    if (confirmed) {
      void run(() => removeRequirement(requirement.id));
    }
  }

  return (
    <div>
      {confirmDialog}
      <p className={HELP_TEXT}>
        設定每個年級各科目每週需要的節數，同年級的每個班級都適用。開始排課的「科目需求」步驟會自動帶入這裡的設定。
      </p>
      <label className="mb-3 flex flex-col gap-1">
        <span className={LABEL}>年級</span>
        <select
          value={gradeId}
          onChange={(event) => setGradeId(Number(event.target.value))}
          aria-label="年級"
          className={`${SELECT} ${FIELD_PAGE}`}
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
              {isAdmin && <th className={TH_ACTIONS}>操作</th>}
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
                      className={`${SELECT} w-full`}
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
                  <td className={TD_ACTIONS}>
                    <div className={ROW_ACTIONS_END}>
                      <DeleteIconButton
                        label={deleteButtonLabel("gradeRequirement", requirementName(requirement))}
                        onClick={() => void handleDelete(requirement)}
                        disabled={isPending}
                      />
                    </div>
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
        <p className="mt-3">
          <button type="button" onClick={() => setIsAdding(true)} disabled={isPending} className={BUTTON_PRIMARY}>
            新增科目需求
          </button>
        </p>
      )}
      {isAdding && (
        <RequirementCreateDialog
          gradeId={gradeId}
          gradeName={gradeName}
          subjects={subjects}
          usedSubjectIds={usedSubjectIds}
          onSaved={() => {
            setIsAdding(false);
            onSubjectsChanged();
            onChanged();
          }}
          onCancel={() => setIsAdding(false)}
        />
      )}
    </div>
  );
}

// 「新增科目需求」's dialog: the subject's name -- typed freely, the school's
// subjects this grade doesn't have yet offered as suggestions -- and its
// weekly periods. A new name creates that subject first.
function RequirementCreateDialog({
  gradeId,
  gradeName,
  subjects,
  usedSubjectIds,
  onSaved,
  onCancel,
}: {
  gradeId: number;
  gradeName: string;
  subjects: readonly Subject[];
  usedSubjectIds: ReadonlySet<number>;
  onSaved: () => void;
  onCancel: () => void;
}): ReactElement {
  const [name, setName] = useState("");
  const [weeklyPeriods, setWeeklyPeriods] = useState(DEFAULT_WEEKLY_PERIODS);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const suggestions = subjects.filter((subject) => subject.is_active && !usedSubjectIds.has(subject.id));

  async function handleSave(): Promise<void> {
    const subjectName = normalizeSubjectName(name);
    const existing = findSubjectByName(subjects, subjectName);
    if (existing !== undefined && usedSubjectIds.has(existing.id)) {
      setError(`${gradeName}已經有「${subjectName}」的科目需求。`);
      return;
    }
    if (existing !== undefined && !existing.is_active) {
      setError(`科目「${subjectName}」已停用，請先到「科目」頁籤啟用。`);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const subject = existing ?? (await createSubject({ name: subjectName }));
      await createRequirement({ grade_id: gradeId, subject_id: subject.id, weekly_periods: weeklyPeriods });
      onSaved();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
      setIsSaving(false);
    }
  }

  return (
    <ConfirmDialog
      open
      title={`新增${gradeName}的科目需求`}
      confirmLabel="儲存"
      cancelLabel="不儲存"
      busy={isSaving}
      busyLabel="儲存中…"
      confirmDisabled={normalizeSubjectName(name) === ""}
      onConfirm={() => void handleSave()}
      onCancel={onCancel}
    >
      <div className="flex flex-col gap-1">
        <span className={LABEL}>科目名稱</span>
        <SuggestionInput
          value={name}
          suggestions={suggestions.map((subject) => subject.name)}
          onChange={(value) => {
            setName(value);
            setError(null);
          }}
          disabled={isSaving}
          placeholder="可直接輸入新科目，例如：書法"
          ariaLabel="科目名稱"
        />
      </div>
      <label className="flex flex-col gap-1">
        <span className={LABEL}>每週節數</span>
        <select
          value={weeklyPeriods}
          onChange={(event) => setWeeklyPeriods(Number(event.target.value))}
          disabled={isSaving}
          aria-label="每週節數"
          className={`${SELECT} w-full`}
        >
          {WEEKLY_PERIOD_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option} 節
            </option>
          ))}
        </select>
      </label>
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
    </ConfirmDialog>
  );
}
