import { useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { list as listClasses } from "../../api/classes";
import {
  create as createRequirement,
  list as listRequirements,
  remove as removeRequirement,
  update as updateRequirement,
} from "../../api/classSubjectRequirements";
import { list as listGrades } from "../../api/grades";
import { list as listRooms } from "../../api/rooms";
import { listTeachers as listSemesterTeachers } from "../../api/semesterSettings";
import { list as listSubjects } from "../../api/subjects";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import type { Class } from "../../types/class";
import type { ClassSubjectRequirement } from "../../types/classSubjectRequirement";
import type { Grade } from "../../types/grade";
import type { Room } from "../../types/room";
import type { SemesterTeacher } from "../../types/semesterSettings";
import type { Subject } from "../../types/subject";
import {
  NO_PATTERN,
  isLessonPatternOffered,
  lessonPatternOptions,
} from "../../utils/lessonPattern";
import { WEEKLY_PERIOD_OPTIONS } from "../../utils/wizard";
import {
  BUTTON_DANGER_SM,
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_SM,
  BUTTON_SECONDARY,
  BUTTON_SECONDARY_SM,
  CARD,
  ERROR_TEXT,
  HELP_TEXT,
  LABEL,
  LOADING_TEXT,
  LOCK_BADGE,
  MUTED_TEXT,
  SELECT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TH,
} from "../../styles/ui";

// Task 98, wizard steps 10-13: for each class, the subjects it needs this
// semester (only the school's existing subjects), 1-6 periods a week, the
// lesson pattern (連堂, offered by the number of periods; optional), the
// teacher (one taking part in the semester; optional -- then any teacher
// still under their maximum) and the special room (one of the school's
// rooms; 原班教室 otherwise). Each row is saved on its own.
export default function RequirementsStep({
  semesterId,
  onBack,
  onNext,
}: {
  semesterId: number;
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const grades = useResource(() => listGrades(0, 1000), []);
  const classes = useResource(() => listClasses(0, 1000), []);
  const subjects = useResource(() => listSubjects(0, 1000), []);
  const rooms = useResource(() => listRooms(0, 1000), []);
  const teachers = useResource(() => listSemesterTeachers(semesterId), [semesterId]);
  const requirements = useResource(
    () => listRequirements(0, 1000, { semester_id: semesterId }),
    [semesterId],
  );

  const errorMessage =
    grades.errorMessage ??
    classes.errorMessage ??
    subjects.errorMessage ??
    rooms.errorMessage ??
    teachers.errorMessage ??
    requirements.errorMessage;
  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  if (
    grades.data === null ||
    classes.data === null ||
    subjects.data === null ||
    rooms.data === null ||
    teachers.data === null ||
    requirements.data === null
  ) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  const levelOf = new Map(grades.data.map((grade: Grade) => [grade.id, grade.level]));
  return (
    <RequirementsForm
      key={semesterId}
      semesterId={semesterId}
      classes={classes.data
        .filter((item) => item.is_active)
        .sort((a, b) => (levelOf.get(a.grade_id) ?? 0) - (levelOf.get(b.grade_id) ?? 0) || a.id - b.id)}
      subjects={subjects.data.filter((subject) => subject.is_active)}
      rooms={rooms.data.filter((room) => room.is_active)}
      teachers={teachers.data}
      initialRequirements={requirements.data}
      onBack={onBack}
      onNext={onNext}
    />
  );
}

function RequirementsForm({
  semesterId,
  classes,
  subjects,
  rooms,
  teachers,
  initialRequirements,
  onBack,
  onNext,
}: {
  semesterId: number;
  classes: readonly Class[];
  subjects: readonly Subject[];
  rooms: readonly Room[];
  teachers: readonly SemesterTeacher[];
  initialRequirements: readonly ClassSubjectRequirement[];
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const [requirements, setRequirements] = useState<ClassSubjectRequirement[]>(() => [...initialRequirements]);
  const [classId, setClassId] = useState<number | null>(classes[0]?.id ?? null);
  const [isAdding, setIsAdding] = useState(false);

  const classRequirements = requirements
    .filter((requirement) => requirement.class_id === classId)
    .sort((a, b) => a.id - b.id);
  const classesWithout = classes.filter(
    (item) => !requirements.some((requirement) => requirement.class_id === item.id),
  );

  function replaceRequirement(saved: ClassSubjectRequirement): void {
    setRequirements((previous) =>
      previous.some((item) => item.id === saved.id)
        ? previous.map((item) => (item.id === saved.id ? saved : item))
        : [...previous, saved],
    );
  }

  return (
    <div className={CARD}>
      <p className={HELP_TEXT}>
        為每個班級設定需要的科目與每週節數，需要時再指定連堂、老師與特殊教室。科目與教室清單來自
        <Link to="/data?tab=subjects" className="font-medium text-blue-600 hover:underline">
          學校資料
        </Link>
        ；不指定特殊教室就在原班教室上課（課表上不顯示），指定了會在課表上註記。
      </p>
      {classes.length === 0 ? (
        <p className={MUTED_TEXT}>還沒有班級，請回上一步建立。</p>
      ) : (
        <>
          <label className="mb-3 flex items-center gap-2">
            <span className={LABEL}>班級</span>
            <select
              value={classId ?? ""}
              onChange={(event) => {
                setClassId(Number(event.target.value));
                setIsAdding(false);
              }}
              className={SELECT}
            >
              {classes.map((item) => {
                const count = requirements.filter((requirement) => requirement.class_id === item.id).length;
                return (
                  <option key={item.id} value={item.id}>
                    {item.name}（{count} 科）
                  </option>
                );
              })}
            </select>
          </label>
          <div className={TABLE_WRAPPER}>
            <table className={TABLE}>
              <thead>
                <tr className={TABLE_HEAD_ROW}>
                  <th className={TH}>科目</th>
                  <th className={TH}>每週節數</th>
                  <th className={TH}>連堂</th>
                  <th className={TH}>指定老師</th>
                  <th className={TH}>特殊教室</th>
                  <th className={TH}>操作</th>
                </tr>
              </thead>
              <tbody>
                {classRequirements.map((requirement) => (
                  <RequirementRow
                    key={requirement.id}
                    semesterId={semesterId}
                    classId={requirement.class_id}
                    requirement={requirement}
                    usedSubjectIds={classRequirements.map((item) => item.subject_id)}
                    subjects={subjects}
                    rooms={rooms}
                    teachers={teachers}
                    onSaved={replaceRequirement}
                    onDeleted={(id) => setRequirements((previous) => previous.filter((item) => item.id !== id))}
                    onCancelNew={() => undefined}
                  />
                ))}
                {isAdding && classId !== null && (
                  <RequirementRow
                    key={`new-${classId}`}
                    semesterId={semesterId}
                    classId={classId}
                    requirement={null}
                    usedSubjectIds={classRequirements.map((item) => item.subject_id)}
                    subjects={subjects}
                    rooms={rooms}
                    teachers={teachers}
                    onSaved={(saved) => {
                      replaceRequirement(saved);
                      setIsAdding(false);
                    }}
                    onDeleted={() => undefined}
                    onCancelNew={() => setIsAdding(false)}
                  />
                )}
              </tbody>
            </table>
          </div>
          <p className="mt-2">
            <button
              type="button"
              onClick={() => setIsAdding(true)}
              disabled={isAdding || subjects.length === 0}
              className={BUTTON_SECONDARY_SM}
            >
              新增科目
            </button>
            {subjects.length === 0 && (
              <span className="ml-2 text-sm text-amber-800">學校還沒有科目，請先到學校資料新增。</span>
            )}
          </p>
          {classesWithout.length > 0 && (
            <p className="mt-3 text-sm text-amber-800">
              還沒有設定科目的班級：{classesWithout.map((item) => item.name).join("、")}
            </p>
          )}
        </>
      )}
      <div className="mt-4 flex gap-2">
        <button type="button" onClick={onBack} className={BUTTON_SECONDARY}>
          上一步
        </button>
        <button type="button" onClick={onNext} disabled={requirements.length === 0} className={BUTTON_PRIMARY}>
          下一步
        </button>
      </div>
    </div>
  );
}

function RequirementRow({
  semesterId,
  classId,
  requirement,
  usedSubjectIds,
  subjects,
  rooms,
  teachers,
  onSaved,
  onDeleted,
  onCancelNew,
}: {
  semesterId: number;
  classId: number;
  // null: a new, unsaved row.
  requirement: ClassSubjectRequirement | null;
  usedSubjectIds: readonly number[];
  subjects: readonly Subject[];
  rooms: readonly Room[];
  teachers: readonly SemesterTeacher[];
  onSaved: (saved: ClassSubjectRequirement) => void;
  onDeleted: (requirementId: number) => void;
  onCancelNew: () => void;
}): ReactElement {
  const [subjectId, setSubjectId] = useState<number | "">(requirement?.subject_id ?? "");
  const [weeklyPeriods, setWeeklyPeriods] = useState(requirement?.weekly_periods ?? 1);
  const [pattern, setPattern] = useState(requirement?.lesson_pattern ?? NO_PATTERN);
  const [teacherId, setTeacherId] = useState<number | "">(requirement?.required_teacher_id ?? "");
  const [roomId, setRoomId] = useState<number | "">(requirement?.required_room_id ?? "");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isLocked = requirement?.is_locked === true;
  const patternOptions = lessonPatternOptions(weeklyPeriods, null);
  const subjectChoices = subjects.filter(
    (subject) => subject.id === requirement?.subject_id || !usedSubjectIds.includes(subject.id),
  );
  const isDirty =
    requirement === null ||
    subjectId !== requirement.subject_id ||
    weeklyPeriods !== requirement.weekly_periods ||
    pattern !== (requirement.lesson_pattern ?? NO_PATTERN) ||
    teacherId !== (requirement.required_teacher_id ?? "") ||
    roomId !== (requirement.required_room_id ?? "");

  function changeWeeklyPeriods(value: number): void {
    setWeeklyPeriods(value);
    if (!isLessonPatternOffered(pattern, lessonPatternOptions(value, null))) {
      setPattern(NO_PATTERN);
    }
  }

  async function handleSave(): Promise<void> {
    if (subjectId === "") {
      return;
    }
    setIsBusy(true);
    setError(null);
    const fields = {
      subject_id: subjectId,
      weekly_periods: weeklyPeriods,
      lesson_pattern: pattern === NO_PATTERN ? null : pattern,
      required_teacher_id: teacherId === "" ? null : teacherId,
      required_room_id: roomId === "" ? null : roomId,
    };
    try {
      onSaved(
        requirement === null
          ? await createRequirement({ semester_id: semesterId, class_id: classId, ...fields })
          : await updateRequirement(requirement.id, fields),
      );
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleDelete(): Promise<void> {
    if (requirement === null || !window.confirm("確定要刪除這個科目需求嗎？")) {
      return;
    }
    setIsBusy(true);
    setError(null);
    try {
      await removeRequirement(requirement.id);
      onDeleted(requirement.id);
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
      setIsBusy(false);
    }
  }

  const disabled = isBusy || isLocked;
  return (
    <tr>
      <td className={TD}>
        <select
          value={subjectId}
          onChange={(event) => setSubjectId(event.target.value === "" ? "" : Number(event.target.value))}
          disabled={disabled}
          aria-label="科目"
          className={SELECT}
        >
          <option value="">請選擇科目</option>
          {subjectChoices.map((subject) => (
            <option key={subject.id} value={subject.id}>
              {subject.name}
            </option>
          ))}
        </select>
      </td>
      <td className={TD}>
        <select
          value={weeklyPeriods}
          onChange={(event) => changeWeeklyPeriods(Number(event.target.value))}
          disabled={disabled}
          aria-label="每週節數"
          className={SELECT}
        >
          {WEEKLY_PERIOD_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option} 節
            </option>
          ))}
        </select>
      </td>
      <td className={TD}>
        {patternOptions.length === 0 ? (
          <span className={MUTED_TEXT}>—</span>
        ) : (
          <select
            value={pattern}
            onChange={(event) => setPattern(event.target.value)}
            disabled={disabled}
            aria-label="連堂"
            className={SELECT}
          >
            {patternOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </td>
      <td className={TD}>
        <select
          value={teacherId}
          onChange={(event) => setTeacherId(event.target.value === "" ? "" : Number(event.target.value))}
          disabled={disabled}
          aria-label="指定老師"
          className={SELECT}
        >
          <option value="">不指定</option>
          {teachers.map((teacher) => (
            <option key={teacher.teacher_id} value={teacher.teacher_id}>
              {teacher.teacher_name}
            </option>
          ))}
        </select>
      </td>
      <td className={TD}>
        <select
          value={roomId}
          onChange={(event) => setRoomId(event.target.value === "" ? "" : Number(event.target.value))}
          disabled={disabled}
          aria-label="特殊教室"
          className={SELECT}
        >
          <option value="">原班教室</option>
          {rooms.map((room) => (
            <option key={room.id} value={room.id}>
              {room.name}
            </option>
          ))}
        </select>
      </td>
      <td className={TD}>
        {isLocked ? (
          <span className={LOCK_BADGE} title="已被已發布或已封存的課表使用，無法修改">
            已鎖定
          </span>
        ) : (
          <div className="flex flex-wrap gap-1">
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={disabled || subjectId === "" || !isDirty}
              className={BUTTON_PRIMARY_SM}
            >
              {requirement === null ? "新增" : "儲存"}
            </button>
            {requirement === null ? (
              <button type="button" onClick={onCancelNew} disabled={isBusy} className={BUTTON_SECONDARY_SM}>
                取消
              </button>
            ) : (
              <button type="button" onClick={() => void handleDelete()} disabled={disabled} className={BUTTON_DANGER_SM}>
                刪除
              </button>
            )}
          </div>
        )}
        {error !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {error}
          </p>
        )}
      </td>
    </tr>
  );
}
