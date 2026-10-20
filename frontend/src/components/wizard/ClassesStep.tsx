import { useState, type ReactElement } from "react";
import { create as createClass, list as listClasses } from "../../api/classes";
import { list as listGrades } from "../../api/grades";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import type { Class } from "../../types/class";
import type { Grade } from "../../types/grade";
import { classNameSuggestions } from "../../utils/wizard";
import {
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_SM,
  BUTTON_SECONDARY,
  CARD,
  ERROR_TEXT,
  HELP_TEXT,
  INPUT,
  LOADING_TEXT,
  MUTED_TEXT,
  SUBSECTION_TITLE,
} from "../../styles/ui";

// Task 98, wizard step 9: the classes of each grade, added one at a time.
// The name box suggests 「一年1班」/「一年甲班」/「一年忠班」... (type 甲 or
// 忠 to filter) but takes any name.
export default function ClassesStep({
  onBack,
  onNext,
}: {
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
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
    <ClassesForm
      grades={[...grades.data].sort((a, b) => a.level - b.level)}
      initialClasses={classes.data}
      onBack={onBack}
      onNext={onNext}
    />
  );
}

function ClassesForm({
  grades,
  initialClasses,
  onBack,
  onNext,
}: {
  grades: readonly Grade[];
  initialClasses: readonly Class[];
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const [classes, setClasses] = useState<Class[]>(() => [...initialClasses]);
  const activeClassCount = classes.filter((item) => item.is_active).length;

  return (
    <div className={CARD}>
      <p className={HELP_TEXT}>
        為每個年級逐一建立班級。名稱可以從清單選，也可以自己輸入；要改名、停用或設定導師教室（原班教室）請到學校資料的班級分頁。
      </p>
      {grades.length === 0 && <p className={MUTED_TEXT}>還沒有年級，請回上一步建立。</p>}
      <div className="flex flex-col gap-4">
        {grades.map((grade) => (
          <GradeClasses
            key={grade.id}
            grade={grade}
            classes={classes.filter((item) => item.grade_id === grade.id)}
            onCreated={(created) => setClasses((previous) => [...previous, created])}
          />
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        <button type="button" onClick={onBack} className={BUTTON_SECONDARY}>
          上一步
        </button>
        <button type="button" onClick={onNext} disabled={activeClassCount === 0} className={BUTTON_PRIMARY}>
          下一步
        </button>
      </div>
    </div>
  );
}

function GradeClasses({
  grade,
  classes,
  onCreated,
}: {
  grade: Grade;
  classes: readonly Class[];
  onCreated: (created: Class) => void;
}): ReactElement {
  const [name, setName] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listId = `class-names-${grade.id}`;
  const trimmed = name.trim();
  const isDuplicate = classes.some((item) => item.name === trimmed);

  async function handleAdd(): Promise<void> {
    setIsSaving(true);
    setError(null);
    try {
      onCreated(await createClass({ grade_id: grade.id, name: trimmed }));
      setName("");
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section>
      <h3 className={SUBSECTION_TITLE}>{grade.name}</h3>
      <p className="mb-2 text-sm text-gray-700">
        {classes.length === 0
          ? "尚無班級"
          : classes.map((item) => (item.is_active ? item.name : `${item.name}（停用）`)).join("、")}
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void handleAdd();
        }}
        className="flex flex-wrap items-center gap-2"
      >
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          list={listId}
          placeholder="輸入或選擇班級名稱"
          aria-label={`${grade.name}新班級名稱`}
          className={`${INPUT} w-48`}
        />
        <datalist id={listId}>
          {classNameSuggestions(grade.level).map((suggestion) => (
            <option key={suggestion} value={suggestion} />
          ))}
        </datalist>
        <button
          type="submit"
          disabled={isSaving || trimmed === "" || isDuplicate}
          className={BUTTON_PRIMARY_SM}
        >
          {isSaving ? "新增中…" : "新增班級"}
        </button>
        {isDuplicate && <span className="text-sm text-amber-800">這個年級已有同名班級</span>}
      </form>
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
    </section>
  );
}
