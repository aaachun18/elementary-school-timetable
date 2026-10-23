import { useState, type ReactElement } from "react";
import { create as createClass, list as listClasses, remove as removeClass } from "../../api/classes";
import { list as listGrades } from "../../api/grades";
import { extractApiErrorMessage, extractDeleteSteps } from "../../constants/errorMessages";
import { RowErrorText } from "../DeleteStepsHint";
import ClassBatchCreateDialog from "./ClassBatchCreateDialog";
import { deleteConfirmOptions, useConfirm } from "../../hooks/useConfirm";
import { useResource } from "../../hooks/useResource";
import type { Class } from "../../types/class";
import type { Grade } from "../../types/grade";
import {
  CLASS_NAME_STYLES,
  CLASS_NAME_STYLE_LABELS,
  classNameOptions,
  type ClassNameStyle,
} from "../../utils/schoolStructure";
import {
  BUTTON_DANGER_SM,
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_SM,
  BUTTON_SECONDARY,
  BUTTON_SECONDARY_SM,
  ERROR_TEXT,
  FIELD_PAGE,
  HELP_TEXT,
  LABEL,
  LOADING_TEXT,
  ROW_ACTIONS,
  SELECT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TH,
  TR_HOVER,
} from "../../styles/ui";

const ALL_GRADES = "all";

// 學校資料 > 班級: a class is only added (grade -> name style -> one of the
// names expanded from the grade, e.g. 一年甲班; or 批次新增 several at once)
// and deleted, never edited.
// The grade list is the school's own (國小 1-6 / 國中 7-9 / 高中 1-3), and
// names already used in a grade are not offered again -- the backend
// refuses both anyway.
export default function ClassesTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const grades = useResource(() => listGrades(0, 1000), []);
  const classes = useResource(() => listClasses(0, 1000), []);

  const errorMessage = grades.errorMessage ?? classes.errorMessage;
  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  if (grades.data === null || classes.data === null) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  return (
    <ClassesTable
      isAdmin={isAdmin}
      grades={[...grades.data].sort((a, b) => a.level - b.level)}
      classes={classes.data}
      onChanged={classes.reload}
    />
  );
}

function ClassesTable({
  isAdmin,
  grades,
  classes,
  onChanged,
}: {
  isAdmin: boolean;
  grades: readonly Grade[];
  classes: readonly Class[];
  onChanged: () => void;
}): ReactElement {
  const [gradeFilter, setGradeFilter] = useState<string>(ALL_GRADES);
  const [isAdding, setIsAdding] = useState(false);
  const [isBatchAdding, setIsBatchAdding] = useState(false);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; message: string; steps: string[] } | null>(null);
  const { confirm, dialog: confirmDialog } = useConfirm();

  const gradeById = new Map(grades.map((grade) => [grade.id, grade]));
  const levelOf = (classItem: Class): number => gradeById.get(classItem.grade_id)?.level ?? 0;
  const shown = classes
    .filter((classItem) => gradeFilter === ALL_GRADES || classItem.grade_id === Number(gradeFilter))
    .sort((a, b) => levelOf(a) - levelOf(b) || a.id - b.id);

  async function handleDelete(classItem: Class): Promise<void> {
    if (!(await confirm(deleteConfirmOptions(classItem.name)))) {
      return;
    }
    setPendingId(classItem.id);
    setRowError(null);
    try {
      await removeClass(classItem.id);
      onChanged();
    } catch (caught) {
      setRowError({ id: classItem.id, message: extractApiErrorMessage(caught), steps: extractDeleteSteps(caught) });
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div>
      {confirmDialog}
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1">
          <span className={LABEL}>年級</span>
          <select
            value={gradeFilter}
            onChange={(event) => setGradeFilter(event.target.value)}
            aria-label="篩選年級"
            className={`${SELECT} ${FIELD_PAGE}`}
          >
            <option value={ALL_GRADES}>全部年級</option>
            {grades.map((grade) => (
              <option key={grade.id} value={grade.id}>
                {grade.name}
              </option>
            ))}
          </select>
        </label>
        {isAdmin && (
          <div className={ROW_ACTIONS}>
            <button
              type="button"
              onClick={() => setIsAdding(true)}
              disabled={isAdding}
              className={BUTTON_PRIMARY}
            >
              新增
            </button>
            <button type="button" onClick={() => setIsBatchAdding(true)} className={BUTTON_SECONDARY}>
              批次新增
            </button>
          </div>
        )}
      </div>
      <div className={TABLE_WRAPPER}>
        <table className={TABLE}>
          <thead>
            <tr className={TABLE_HEAD_ROW}>
              <th className={TH}>年級</th>
              <th className={TH}>名稱類型</th>
              <th className={TH}>班級名稱</th>
              {isAdmin && <th className={TH}>操作</th>}
            </tr>
          </thead>
          <tbody>
            {isAdding && (
              <ClassNewRow
                grades={grades}
                classes={classes}
                initialGradeId={gradeFilter === ALL_GRADES ? null : Number(gradeFilter)}
                onCreated={() => {
                  setIsAdding(false);
                  onChanged();
                }}
                onCancel={() => setIsAdding(false)}
              />
            )}
            {shown.map((classItem) => (
              <tr key={classItem.id} className={TR_HOVER}>
                <td className={TD}>{gradeById.get(classItem.grade_id)?.name ?? "—"}</td>
                <td className={TD}>{CLASS_NAME_STYLE_LABELS[classItem.name_style]}</td>
                <td className={TD}>{classItem.name}</td>
                {isAdmin && (
                  <td className={TD}>
                    <button
                      type="button"
                      onClick={() => void handleDelete(classItem)}
                      disabled={pendingId !== null}
                      className={BUTTON_DANGER_SM}
                    >
                      {pendingId === classItem.id ? "刪除中…" : "刪除"}
                    </button>
                    {rowError?.id === classItem.id && (
                      <RowErrorText message={rowError.message} deleteSteps={rowError.steps} />
                    )}
                  </td>
                )}
              </tr>
            ))}
            {shown.length === 0 && !isAdding && (
              <tr>
                <td className={TD} colSpan={isAdmin ? 4 : 3}>
                  <span className={HELP_TEXT}>目前沒有班級。</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {isBatchAdding && (
        <ClassBatchCreateDialog
          grades={grades}
          classes={classes}
          initialGradeId={gradeFilter === ALL_GRADES ? null : Number(gradeFilter)}
          onCreated={() => {
            setIsBatchAdding(false);
            onChanged();
          }}
          onCancel={() => setIsBatchAdding(false)}
        />
      )}
    </div>
  );
}

function ClassNewRow({
  grades,
  classes,
  initialGradeId,
  onCreated,
  onCancel,
}: {
  grades: readonly Grade[];
  classes: readonly Class[];
  initialGradeId: number | null;
  onCreated: () => void;
  onCancel: () => void;
}): ReactElement {
  const [gradeId, setGradeId] = useState<number | null>(initialGradeId);
  const [nameStyle, setNameStyle] = useState<ClassNameStyle | null>(null);
  const [name, setName] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const grade = grades.find((item) => item.id === gradeId);
  const usedNames = new Set(classes.filter((item) => item.grade_id === gradeId).map((item) => item.name));
  const nameOptions =
    grade === undefined || nameStyle === null
      ? []
      : classNameOptions(grade.level, nameStyle).filter((option) => !usedNames.has(option));

  async function handleConfirm(): Promise<void> {
    if (gradeId === null || nameStyle === null || name === "") {
      return;
    }
    setIsPending(true);
    setError(null);
    try {
      await createClass({ grade_id: gradeId, name_style: nameStyle, name });
      onCreated();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
      setIsPending(false);
    }
  }

  return (
    <tr className="bg-blue-50/40">
      <td className={TD}>
        <select
          value={gradeId ?? ""}
          onChange={(event) => {
            setGradeId(event.target.value === "" ? null : Number(event.target.value));
            setName("");
          }}
          disabled={isPending}
          aria-label="年級"
          className={`${SELECT} w-full`}
        >
          <option value="">請選擇年級</option>
          {grades.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </td>
      <td className={TD}>
        <select
          value={nameStyle ?? ""}
          onChange={(event) => {
            setNameStyle(event.target.value === "" ? null : (event.target.value as ClassNameStyle));
            setName("");
          }}
          disabled={isPending || gradeId === null}
          aria-label="名稱類型"
          className={`${SELECT} w-full`}
        >
          <option value="">請選擇名稱類型</option>
          {CLASS_NAME_STYLES.map((style) => (
            <option key={style} value={style}>
              {CLASS_NAME_STYLE_LABELS[style]}
            </option>
          ))}
        </select>
      </td>
      <td className={TD}>
        <select
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending || nameStyle === null}
          aria-label="班級名稱"
          className={`${SELECT} w-full`}
        >
          <option value="">請選擇班級名稱</option>
          {nameOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </td>
      <td className={TD}>
        <div className={ROW_ACTIONS}>
          <button
            type="button"
            onClick={() => void handleConfirm()}
            disabled={isPending || name === ""}
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
        </div>
        {error !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {error}
          </p>
        )}
      </td>
    </tr>
  );
}
