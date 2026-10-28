import { useId, useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { list as listClasses } from "../../api/classes";
import { list as listGrades } from "../../api/grades";
import { list as listTeachers } from "../../api/teachers";
import { list as listTimeSlots } from "../../api/timeSlots";
import { listTeachers as listSemesterTeachers, replaceTeachers } from "../../api/semesterSettings";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import { useTeacherNames } from "../../hooks/useTeacherAccounts";
import type { Class } from "../../types/class";
import type { SemesterTeacher, SemesterTeacherEntry } from "../../types/semesterSettings";
import type { Teacher } from "../../types/teacher";
import type { TimeSlot } from "../../types/timeSlot";
import { classesWithoutHomeroom, missingHomeroomMessage, sortClassesByGrade } from "../../utils/homeroom";
import { saveTeachersDisabledReason } from "../../utils/disabledReason";
import { DEFAULT_MAX_WEEKLY_PERIODS, periodsRangeError, wizardStepLabel } from "../../utils/wizard";
import ActionBar from "../ActionBar";
import CardHeader from "../CardHeader";
import DisabledReason from "../DisabledReason";
import TimeSlotPickerDialog from "./TimeSlotPickerDialog";
import {
  BUTTON_PRIMARY,
  BUTTON_GHOST_SM,
  CARD,
  CHECKBOX,
  ERROR_TEXT,
  HOMEROOM_TAG,
  INPUT,
  LINK_TEXT,
  LOADING_TEXT,
  MUTED_TEXT,
  SELECT,
  TEACHER_CARD,
  TEACHER_CARD_CHECKED,
  TEACHER_GRID,
  TOOLBAR,
} from "../../styles/ui";

interface Draft {
  checked: boolean;
  minText: string;
  maxText: string;
  unavailable: number[];
  // The class this teacher is 導師 of, if any (only kept while checked).
  homeroomClassId: number | null;
}

function initialDrafts(
  teachers: readonly Teacher[],
  current: readonly SemesterTeacher[],
): Map<number, Draft> {
  const byTeacher = new Map(current.map((item) => [item.teacher_id, item]));
  return new Map(
    teachers.map((teacher) => {
      const saved = byTeacher.get(teacher.id);
      return [
        teacher.id,
        {
          checked: saved !== undefined,
          minText: String(saved?.min_weekly_periods ?? 0),
          maxText: String(saved?.max_weekly_periods ?? DEFAULT_MAX_WEEKLY_PERIODS),
          unavailable: saved?.unavailable_time_slot_ids ?? [],
          homeroomClassId: saved?.homeroom_class_id ?? null,
        },
      ];
    }),
  );
}

// Task 98, wizard steps 4-6: which 啟用 teacher accounts take part in this
// 排課紀錄 (a grid of checkboxes), each one's weekly minimum / maximum, and
// the slots they can't teach (a timetable-shaped dialog). Saved together
// with 「儲存並下一步」 (PUT /schedule-versions/{id}/teachers, the complete list).
// Each teacher can also be made 導師 of one class (a dropdown of the classes
// still without one; picking a class takes the teacher part). Every class
// needs a 導師 before 下一步; not every teacher has to be one.
export default function TeachersStep({
  versionId,
  onNext,
}: {
  versionId: number;
  onNext: () => void;
}): ReactElement {
  const teachers = useResource(() => listTeachers(0, 1000), []);
  const current = useResource(() => listSemesterTeachers(versionId), [versionId]);
  const timeSlots = useResource(() => listTimeSlots(0, 1000), []);
  const classes = useResource(() => listClasses(0, 1000), []);
  const grades = useResource(() => listGrades(0, 1000), []);
  const teacherNames = useTeacherNames();

  const errorMessage =
    teachers.errorMessage ??
    current.errorMessage ??
    timeSlots.errorMessage ??
    classes.errorMessage ??
    grades.errorMessage;
  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  if (
    teachers.data === null ||
    current.data === null ||
    timeSlots.data === null ||
    classes.data === null ||
    grades.data === null
  ) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  const gradeLevelById = new Map(grades.data.map((grade) => [grade.id, grade.level]));
  return (
    <TeachersForm
      key={versionId}
      versionId={versionId}
      teachers={teachers.data.filter((teacher) => teacher.is_active)}
      current={current.data}
      timeSlots={timeSlots.data}
      classes={sortClassesByGrade(classes.data, gradeLevelById)}
      teacherLabel={(teacher) => teacherNames.label(teacher.id, teacher.name)}
      onNext={onNext}
    />
  );
}

function TeachersForm({
  versionId,
  teachers,
  current,
  timeSlots,
  classes,
  teacherLabel,
  onNext,
}: {
  versionId: number;
  teachers: readonly Teacher[];
  current: readonly SemesterTeacher[];
  timeSlots: readonly TimeSlot[];
  classes: readonly Class[];
  // Task 99: 「王老師(teacher11)」 when two teachers share a name.
  teacherLabel: (teacher: Teacher) => string;
  onNext: () => void;
}): ReactElement {
  const [drafts, setDrafts] = useState(() => initialDrafts(teachers, current));
  const [pickerTeacher, setPickerTeacher] = useState<Teacher | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saveReasonId = useId();

  function update(teacherId: number, change: Partial<Draft>): void {
    setDrafts((previous) => {
      const next = new Map(previous);
      const draft = next.get(teacherId);
      if (draft !== undefined) {
        next.set(teacherId, { ...draft, ...change });
      }
      return next;
    });
  }

  const checkedTeachers = teachers.filter((teacher) => drafts.get(teacher.id)?.checked === true);
  const allChecked = teachers.length > 0 && checkedTeachers.length === teachers.length;
  const someChecked = checkedTeachers.length > 0 && !allChecked;

  function setAllChecked(checked: boolean): void {
    setDrafts((previous) => {
      const next = new Map(previous);
      for (const [teacherId, draft] of previous) {
        // Unchecked teachers take no part, so they are no 導師 either.
        next.set(teacherId, { ...draft, checked, homeroomClassId: checked ? draft.homeroomClassId : null });
      }
      return next;
    });
  }
  const rangeErrors = new Map(
    checkedTeachers.map((teacher) => {
      const draft = drafts.get(teacher.id) as Draft;
      return [teacher.id, periodsRangeError(draft.minText, draft.maxText)];
    }),
  );
  const hasRangeError = [...rangeErrors.values()].some((message) => message !== null);
  const saveDisabledReason = saveTeachersDisabledReason({
    isSaving,
    checkedCount: checkedTeachers.length,
    hasRangeError,
  });

  const classById = new Map(classes.map((item) => [item.id, item]));
  const assignedClassIds = new Set(
    checkedTeachers
      .map((teacher) => drafts.get(teacher.id)?.homeroomClassId ?? null)
      .filter((classId): classId is number => classId !== null),
  );
  const freeClasses = classesWithoutHomeroom(classes, assignedClassIds);

  async function handleSave(): Promise<void> {
    const homeroomMessage = missingHomeroomMessage(classes, assignedClassIds);
    if (homeroomMessage !== null) {
      setError(homeroomMessage);
      return;
    }
    setIsSaving(true);
    setError(null);
    const entries: SemesterTeacherEntry[] = checkedTeachers.map((teacher) => {
      const draft = drafts.get(teacher.id) as Draft;
      return {
        teacher_id: teacher.id,
        min_weekly_periods: Number(draft.minText),
        max_weekly_periods: Number(draft.maxText),
        unavailable_time_slot_ids: draft.unavailable,
        homeroom_class_id: draft.homeroomClassId,
      };
    });
    try {
      await replaceTeachers(versionId, entries);
      onNext();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <>
      <div className={CARD}>
        <CardHeader
          title={wizardStepLabel("teachers")}
          info={
            <p>
              勾選要納入這次排課的老師，設定每週最低與最高節數，並標出沒辦法排課的時間。沒有指定老師的課程，會分給還沒超過上限的老師。
              名單是所有啟用中的一般老師帳號，要新增老師請到
              <Link to="/users" className={LINK_TEXT}>
                帳號管理
              </Link>
              。
            </p>
          }
        />
        {teachers.length === 0 ? (
          <p className={MUTED_TEXT}>
            目前沒有啟用中的一般老師帳號，請先到
            <Link to="/users" className={LINK_TEXT}>
              帳號管理
            </Link>
            建立老師帳號，再回來勾選。
          </p>
        ) : (
          <>
            <div className={TOOLBAR}>
              <label className="inline-flex min-h-8 cursor-pointer items-center gap-2 text-sm font-medium text-gray-900">
                <input
                  type="checkbox"
                  checked={allChecked}
                  ref={(element) => {
                    if (element !== null) {
                      element.indeterminate = someChecked;
                    }
                  }}
                  onChange={(event) => setAllChecked(event.target.checked)}
                  className={CHECKBOX}
                />
                全選
              </label>
              <span className="text-sm text-gray-700" aria-live="polite">
                已納入 {checkedTeachers.length} 位老師 · {assignedClassIds.size}/{classes.length} 個班級已指派導師
              </span>
            </div>
            <div className={TEACHER_GRID}>
              {teachers.map((teacher) => {
                const draft = drafts.get(teacher.id) as Draft;
                const rangeError = rangeErrors.get(teacher.id) ?? null;
                return (
                  <div key={teacher.id} className={draft.checked ? TEACHER_CARD_CHECKED : TEACHER_CARD}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <label className="flex min-h-8 cursor-pointer items-center gap-2 text-sm font-medium">
                        <input
                          type="checkbox"
                          checked={draft.checked}
                          onChange={(event) =>
                            update(teacher.id, {
                              checked: event.target.checked,
                              homeroomClassId: event.target.checked ? draft.homeroomClassId : null,
                            })
                          }
                          className={CHECKBOX}
                        />
                        {teacherLabel(teacher)}
                        {draft.homeroomClassId !== null && (
                          <span className={HOMEROOM_TAG}>{classById.get(draft.homeroomClassId)?.name ?? "—"}</span>
                        )}
                      </label>
                      {draft.homeroomClassId === null ? (
                        <select
                          value=""
                          onChange={(event) => {
                            if (event.target.value !== "") {
                              update(teacher.id, { checked: true, homeroomClassId: Number(event.target.value) });
                              setError(null);
                            }
                          }}
                          disabled={freeClasses.length === 0}
                          aria-label={`${teacherLabel(teacher)}擔任導師的班級`}
                          className={`${SELECT} w-32 text-xs`}
                        >
                          <option value="">設定導師班級</option>
                          {freeClasses.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        // Task 98 Phase B: only takes this teacher off the
                        // class as 導師 in this form (nothing is saved until
                        // 「儲存並下一步」, and the class is back in the
                        // dropdown at once) -- so no confirmation.
                        <button
                          type="button"
                          onClick={() => {
                            update(teacher.id, { homeroomClassId: null });
                            setError(null);
                          }}
                          aria-label={`取消${teacherLabel(teacher)}的導師班級`}
                          className={BUTTON_GHOST_SM}
                        >
                          取消導師班級
                        </button>
                      )}
                    </div>
                    {draft.checked && (
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                        <label className="inline-flex items-center gap-1">
                          每週最低
                          <input
                            type="number"
                            min={0}
                            value={draft.minText}
                            onChange={(event) => update(teacher.id, { minText: event.target.value })}
                            aria-label={`${teacherLabel(teacher)}每週最低節數`}
                            className={`${INPUT} w-16`}
                          />
                        </label>
                        <label className="inline-flex items-center gap-1">
                          最高
                          <input
                            type="number"
                            min={0}
                            value={draft.maxText}
                            onChange={(event) => update(teacher.id, { maxText: event.target.value })}
                            aria-label={`${teacherLabel(teacher)}每週最高節數`}
                            className={`${INPUT} w-16`}
                          />
                          節
                        </label>
                        <button
                          type="button"
                          onClick={() => setPickerTeacher(teacher)}
                          className={BUTTON_GHOST_SM}
                        >
                          不可排時段（{draft.unavailable.length}）
                        </button>
                        {rangeError !== null && <p className={`${ERROR_TEXT} w-full`}>{rangeError}</p>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
        {error !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {error}
          </p>
        )}
        {pickerTeacher !== null && (
          <TimeSlotPickerDialog
            key={pickerTeacher.id}
            title={`${teacherLabel(pickerTeacher)}的不可排課時段`}
            description="勾選這學期沒辦法排課的節次，排課時會避開。"
            checkedLabel="不可排課"
            timeSlots={timeSlots}
            initialSelected={drafts.get(pickerTeacher.id)?.unavailable ?? []}
            busy={false}
            errorMessage={null}
            requireOne={false}
            onSave={(ids) => {
              update(pickerTeacher.id, { unavailable: ids });
              setPickerTeacher(null);
            }}
            onCancel={() => setPickerTeacher(null)}
          />
        )}
      </div>
      {/* Task 100: no 上一步 -- step 1's semester is fixed once the record
          exists, so there is nothing to go back to. */}
      <ActionBar
        end={
          <>
            <DisabledReason id={saveReasonId} reason={saveDisabledReason} />
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={isSaving || saveDisabledReason !== null}
              title={saveDisabledReason ?? undefined}
              aria-describedby={saveDisabledReason !== null ? saveReasonId : undefined}
              className={BUTTON_PRIMARY}
            >
              {isSaving ? "儲存中…" : "儲存並下一步"}
            </button>
          </>
        }
      />
    </>
  );
}
