import { useState, type ReactElement } from "react";
import { createBatch } from "../../api/classes";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import type { Class } from "../../types/class";
import type { Grade } from "../../types/grade";
import {
  CLASS_NAME_STYLES,
  CLASS_NAME_STYLE_LABELS,
  unusedClassNames,
  type ClassNameStyle,
} from "../../utils/schoolStructure";
import ConfirmDialog from "../ConfirmDialog";
import { ERROR_TEXT, HELP_TEXT, LABEL, SELECT } from "../../styles/ui";

// 學校資料 > 班級 > 批次新增: grade, then name style, then how many. Only as
// many as the style has left can be picked (甲乙丙 10、忠孝仁愛 8、一二三
// 30, minus the grade's classes of that style), and they continue after
// the existing ones (一年甲班、一年乙班 exist -> 一年丙班 ...). The backend
// picks the same names and creates all of them or none.
export default function ClassBatchCreateDialog({
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
  const [count, setCount] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const grade = grades.find((item) => item.id === gradeId);
  const usedNames = new Set(classes.filter((item) => item.grade_id === gradeId).map((item) => item.name));
  const freeNames = grade === undefined || nameStyle === null ? [] : unusedClassNames(grade.level, nameStyle, usedNames);
  const newNames = count === null ? [] : freeNames.slice(0, count);

  async function handleConfirm(): Promise<void> {
    if (gradeId === null || nameStyle === null || count === null) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await createBatch({ grade_id: gradeId, name_style: nameStyle, count });
      onCreated();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
      setIsSaving(false);
    }
  }

  return (
    <ConfirmDialog
      open
      title="批次新增班級"
      confirmLabel="新增班級"
      cancelLabel="不新增"
      busy={isSaving}
      busyLabel="新增中…"
      confirmDisabled={count === null}
      onConfirm={() => void handleConfirm()}
      onCancel={onCancel}
    >
      <label className="flex flex-col gap-1">
        <span className={LABEL}>年級</span>
        <select
          value={gradeId ?? ""}
          onChange={(event) => {
            setGradeId(event.target.value === "" ? null : Number(event.target.value));
            setCount(null);
          }}
          disabled={isSaving}
          className={`${SELECT} w-full`}
        >
          <option value="">請選擇年級</option>
          {grades.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className={LABEL}>名稱類型</span>
        <select
          value={nameStyle ?? ""}
          onChange={(event) => {
            setNameStyle(event.target.value === "" ? null : (event.target.value as ClassNameStyle));
            setCount(null);
          }}
          disabled={isSaving || gradeId === null}
          className={`${SELECT} w-full`}
        >
          <option value="">請選擇名稱類型</option>
          {CLASS_NAME_STYLES.map((style) => (
            <option key={style} value={style}>
              {CLASS_NAME_STYLE_LABELS[style]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className={LABEL}>新增幾班</span>
        <select
          value={count ?? ""}
          onChange={(event) => setCount(event.target.value === "" ? null : Number(event.target.value))}
          disabled={isSaving || freeNames.length === 0}
          className={`${SELECT} w-full`}
        >
          <option value="">請選擇班數</option>
          {freeNames.map((_, index) => (
            <option key={index + 1} value={index + 1}>
              {index + 1} 班
            </option>
          ))}
        </select>
      </label>
      {grade !== undefined && nameStyle !== null && freeNames.length === 0 && (
        <p className={HELP_TEXT}>
          {grade.name}的「{CLASS_NAME_STYLE_LABELS[nameStyle]}」班級已經全部建立，無法再新增。
        </p>
      )}
      {newNames.length > 0 && <p className={HELP_TEXT}>將新增：{newNames.join("、")}</p>}
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
    </ConfirmDialog>
  );
}
