import { useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { list as listClasses } from "../../api/classes";
import {
  list as listRequirements,
  syncWithSchool,
  update as updateRequirement,
} from "../../api/classSubjectRequirements";
import { list as listGrades } from "../../api/grades";
import { list as listLessons } from "../../api/lessons";
import { list as listTimeSlots } from "../../api/timeSlots";
import { list as listRooms } from "../../api/rooms";
import { listTeachers as listSemesterTeachers } from "../../api/semesterSettings";
import { list as listSubjects } from "../../api/subjects";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import type { Class } from "../../types/class";
import type {
  ClassSubjectRequirement,
  ClassSubjectRequirementUpdate,
  RequirementSyncResult,
} from "../../types/classSubjectRequirement";
import type { Grade } from "../../types/grade";
import type { Room } from "../../types/room";
import type { SemesterTeacher } from "../../types/semesterSettings";
import type { Subject } from "../../types/subject";
import type { TimeSlot } from "../../types/timeSlot";
import { NO_PATTERN, lessonPatternOptions } from "../../utils/lessonPattern";
import { buildPeriodDisplay } from "../../utils/periodDisplay";
import ActionBar from "../ActionBar";
import CardHeader from "../CardHeader";
import FixedSlotsDialog from "./FixedSlotsDialog";
import { wizardStepLabel } from "../../utils/wizard";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  BUTTON_GHOST_SM,
  CARD,
  ERROR_TEXT,
  FIELD_PAGE,
  LABEL,
  LINK_TEXT,
  LOADING_TEXT,
  LOCK_BADGE,
  MUTED_TEXT,
  NOTICE,
  REQ_COL_FIXED,
  REQ_COL_PATTERN,
  REQ_COL_ROOM,
  REQ_COL_TEACHER,
  RULE_NOTE,
  SELECT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TAB_BUTTON,
  TAB_BUTTON_ACTIVE,
  TD,
  TD_NOWRAP,
  TH,
} from "../../styles/ui";

const CLASS_BUTTON = `${TAB_BUTTON} text-left`;
const CLASS_BUTTON_ACTIVE = `${TAB_BUTTON_ACTIVE} text-left`;

// Task 98, wizard 科目需求 step: every class's subjects and weekly periods
// come from the school's 科目需求 (學校資料) -- opening the step syncs them
// into the 排課紀錄 (POST /class-subject-requirements/sync) -- so here only
// the lesson pattern (連堂, offered by the number of periods; optional), the
// teacher (one taking part in the record; optional -- then any teacher
// still under their maximum) and the special room (one of the school's
// rooms; 原班教室 otherwise) are set, and -- 固定時段, the column after
// 連堂 -- which of its lessons are pinned to a time slot. Each change is
// saved right away.
// Classes are picked per grade: a grade dropdown, then that grade's classes
// listed on the left.
export default function RequirementsStep({
  versionId,
  onBack,
  onNext,
}: {
  versionId: number;
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  // The sync runs first; the requirements are read after it.
  const synced = useResource(() => syncWithSchool(versionId), [versionId]);
  const grades = useResource(() => listGrades(0, 1000), []);
  const classes = useResource(() => listClasses(0, 1000), []);
  const subjects = useResource(() => listSubjects(0, 1000), []);
  const rooms = useResource(() => listRooms(0, 1000), []);
  const teachers = useResource(() => listSemesterTeachers(versionId), [versionId]);
  const timeSlots = useResource(() => listTimeSlots(0, 1000), []);

  const errorMessage =
    synced.errorMessage ??
    grades.errorMessage ??
    classes.errorMessage ??
    subjects.errorMessage ??
    rooms.errorMessage ??
    teachers.errorMessage ??
    timeSlots.errorMessage;
  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  if (
    synced.data === null ||
    grades.data === null ||
    classes.data === null ||
    subjects.data === null ||
    rooms.data === null ||
    teachers.data === null ||
    timeSlots.data === null
  ) {
    return <p className={LOADING_TEXT}>正在帶入學校的科目需求…</p>;
  }
  const levelOf = new Map(grades.data.map((grade: Grade) => [grade.id, grade.level]));
  return (
    <SyncedRequirements
      key={versionId}
      versionId={versionId}
      syncResult={synced.data}
      grades={[...grades.data].sort((a, b) => a.level - b.level)}
      classes={[...classes.data].sort(
        (a, b) => (levelOf.get(a.grade_id) ?? 0) - (levelOf.get(b.grade_id) ?? 0) || a.id - b.id,
      )}
      subjects={subjects.data}
      rooms={rooms.data.filter((room) => room.is_active)}
      teachers={teachers.data}
      timeSlots={timeSlots.data}
      onBack={onBack}
      onNext={onNext}
    />
  );
}

function SyncedRequirements({
  versionId,
  ...props
}: {
  versionId: number;
  syncResult: RequirementSyncResult;
  grades: readonly Grade[];
  classes: readonly Class[];
  subjects: readonly Subject[];
  rooms: readonly Room[];
  teachers: readonly SemesterTeacher[];
  timeSlots: readonly TimeSlot[];
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const requirements = useResource(
    () => listRequirements(0, 1000, { schedule_version_id: versionId }),
    [versionId],
  );
  if (requirements.errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {requirements.errorMessage}
      </p>
    );
  }
  if (requirements.data === null) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  return <RequirementsForm versionId={versionId} initialRequirements={requirements.data} {...props} />;
}

function syncSummary(result: RequirementSyncResult): string | null {
  const parts = [
    result.created > 0 ? `新增 ${result.created} 筆` : null,
    result.updated > 0 ? `更新 ${result.updated} 筆節數` : null,
    result.removed > 0 ? `移除 ${result.removed} 筆` : null,
  ].filter((part): part is string => part !== null);
  return parts.length === 0 ? null : `已依學校的科目需求${parts.join("、")}。`;
}

function RequirementsForm({
  versionId,
  timeSlots,
  syncResult,
  grades,
  classes,
  subjects,
  rooms,
  teachers,
  initialRequirements,
  onBack,
  onNext,
}: {
  versionId: number;
  timeSlots: readonly TimeSlot[];
  syncResult: RequirementSyncResult;
  grades: readonly Grade[];
  classes: readonly Class[];
  subjects: readonly Subject[];
  rooms: readonly Room[];
  teachers: readonly SemesterTeacher[];
  initialRequirements: readonly ClassSubjectRequirement[];
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const [requirements, setRequirements] = useState<ClassSubjectRequirement[]>(() => [...initialRequirements]);
  const gradesWithClasses = grades.filter((grade) => classes.some((item) => item.grade_id === grade.id));
  const [gradeId, setGradeId] = useState<number | null>(gradesWithClasses[0]?.id ?? null);
  const gradeClasses = classes.filter((item) => item.grade_id === gradeId);
  const [classId, setClassId] = useState<number | null>(gradeClasses[0]?.id ?? null);
  // 固定時段: how many of each requirement's lessons are pinned (reloaded
  // after the dialog closes), and the requirement the dialog is open for.
  const lessons = useResource(() => listLessons(0, 1000, { schedule_version_id: versionId }), [versionId]);
  const [fixing, setFixing] = useState<ClassSubjectRequirement | null>(null);
  const fixedCountOf = new Map<number, number>();
  for (const lesson of lessons.data ?? []) {
    if (lesson.fixed_time_slot_id !== null) {
      fixedCountOf.set(
        lesson.class_subject_requirement_id,
        (fixedCountOf.get(lesson.class_subject_requirement_id) ?? 0) + 1,
      );
    }
  }
  const teachingTimeSlots = [...timeSlots]
    .filter((slot) => slot.is_teaching_period)
    .sort((a, b) => a.weekday - b.weekday || a.period - b.period);
  const periodDisplay = buildPeriodDisplay(timeSlots);

  function selectGrade(nextGradeId: number): void {
    setGradeId(nextGradeId);
    setClassId(classes.find((item) => item.grade_id === nextGradeId)?.id ?? null);
  }

  const subjectName = new Map(subjects.map((subject) => [subject.id, subject.name]));
  const classRequirements = requirements
    .filter((requirement) => requirement.class_id === classId)
    .sort((a, b) => a.subject_id - b.subject_id);
  const classesWithout = classes.filter(
    (item) => !requirements.some((requirement) => requirement.class_id === item.id),
  );
  const summary = syncSummary(syncResult);

  function replaceRequirement(saved: ClassSubjectRequirement): void {
    setRequirements((previous) => previous.map((item) => (item.id === saved.id ? saved : item)));
  }

  return (
    <>
      <div className={CARD}>
        <CardHeader
          title={wizardStepLabel("requirements")}
          info={
            <p>
              每個班級的科目與每週節數會自動帶入
              <Link to="/data?tab=gradeRequirements" className={LINK_TEXT}>
                學校資料的科目需求
              </Link>
              ，要調整請到那裡修改。這裡只需要視情況指定連堂、老師與特殊教室，修改後會立即儲存；不指定特殊教室就在原班教室上課（課表上不顯示），指定了會在課表上註記。
            </p>
          }
        />
        <p className={RULE_NOTE}>修改後會立即儲存</p>
        {summary !== null && <p className={`${NOTICE} mb-3`}>{summary}</p>}
        {classes.length === 0 ? (
          <p className={MUTED_TEXT}>
            還沒有班級，請先到
            <Link to="/data?tab=classes" className={LINK_TEXT}>
              學校資料
            </Link>
            建立。
          </p>
        ) : (
          <>
            <label className="mb-3 flex items-center gap-2">
              <span className={LABEL}>年級</span>
              <select
                value={gradeId ?? ""}
                onChange={(event) => selectGrade(Number(event.target.value))}
                className={`${SELECT} ${FIELD_PAGE}`}
              >
                {gradesWithClasses.map((grade) => (
                  <option key={grade.id} value={grade.id}>
                    {grade.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex flex-col gap-3 md:flex-row md:items-start">
              <nav aria-label="班級" className="flex shrink-0 flex-row flex-wrap gap-1 md:w-40 md:flex-col">
                {gradeClasses.map((item) => {
                  const count = requirements.filter((requirement) => requirement.class_id === item.id).length;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setClassId(item.id)}
                      aria-current={item.id === classId ? "true" : undefined}
                      className={item.id === classId ? CLASS_BUTTON_ACTIVE : CLASS_BUTTON}
                    >
                      {item.name}
                      <span className="ml-1 text-xs text-gray-500">（{count} 科）</span>
                    </button>
                  );
                })}
              </nav>
              <div className="min-w-0 flex-1">
                <div className={TABLE_WRAPPER}>
                  <table className={TABLE}>
                    <thead>
                      <tr className={TABLE_HEAD_ROW}>
                        <th className={TH}>科目</th>
                        <th className={TH}>每週節數</th>
                        <th className={`${TH} ${REQ_COL_PATTERN}`}>連堂</th>
                        <th className={`${TH} ${REQ_COL_FIXED}`}>固定時段</th>
                        <th className={`${TH} ${REQ_COL_TEACHER}`}>指定老師</th>
                        <th className={`${TH} ${REQ_COL_ROOM}`}>特殊教室</th>
                      </tr>
                    </thead>
                    <tbody>
                      {classRequirements.map((requirement) => (
                        <RequirementRow
                          key={requirement.id}
                          requirement={requirement}
                          subjectName={subjectName.get(requirement.subject_id) ?? "—"}
                          rooms={rooms}
                          teachers={teachers}
                          fixedCount={fixedCountOf.get(requirement.id) ?? 0}
                          onOpenFixed={() => setFixing(requirement)}
                          onSaved={replaceRequirement}
                        />
                      ))}
                      {classRequirements.length === 0 && (
                        <tr>
                          <td className={TD} colSpan={6}>
                            <span className={MUTED_TEXT}>這個班級的年級還沒有科目需求。</span>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            {classesWithout.length > 0 && (
              <p className="mt-3 text-sm text-amber-800">
                還沒有科目需求的班級：{classesWithout.map((item) => item.name).join("、")}（請到學校資料的科目需求設定該年級）
              </p>
            )}
          </>
        )}
        {fixing !== null && (
          <FixedSlotsDialog
            versionId={versionId}
            requirementId={fixing.id}
            lessonPattern={fixing.lesson_pattern ?? null}
            title={`${classes.find((item) => item.id === fixing.class_id)?.name ?? ""}${subjectName.get(fixing.subject_id) ?? ""}的固定時段`}
            teachingTimeSlots={teachingTimeSlots}
            periodDisplay={periodDisplay}
            onClose={() => {
              setFixing(null);
              lessons.reload();
            }}
          />
        )}
      </div>
      <ActionBar
        start={
          <button type="button" onClick={onBack} className={BUTTON_SECONDARY}>
            上一步
          </button>
        }
        end={
          <button type="button" onClick={onNext} disabled={requirements.length === 0} className={BUTTON_PRIMARY}>
            下一步
          </button>
        }
      />
    </>
  );
}

function RequirementRow({
  requirement,
  subjectName,
  rooms,
  teachers,
  fixedCount,
  onOpenFixed,
  onSaved,
}: {
  requirement: ClassSubjectRequirement;
  subjectName: string;
  rooms: readonly Room[];
  teachers: readonly SemesterTeacher[];
  fixedCount: number;
  onOpenFixed: () => void;
  onSaved: (saved: ClassSubjectRequirement) => void;
}): ReactElement {
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isLocked = requirement.is_locked;
  const patternOptions = lessonPatternOptions(requirement.weekly_periods, null);
  const disabled = isBusy || isLocked;

  async function save(fields: ClassSubjectRequirementUpdate): Promise<void> {
    setIsBusy(true);
    setError(null);
    try {
      onSaved(await updateRequirement(requirement.id, fields));
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <tr>
      <td className={TD}>
        {subjectName}
        {isLocked && (
          <span className={`${LOCK_BADGE} ml-2`} title="已被已發布或已封存的課表使用，無法修改">
            已鎖定
          </span>
        )}
        {error !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {error}
          </p>
        )}
      </td>
      <td className={TD}>{requirement.weekly_periods} 節</td>
      <td className={TD}>
        {patternOptions.length === 0 ? (
          <span className={MUTED_TEXT}>—</span>
        ) : (
          <select
            value={requirement.lesson_pattern ?? NO_PATTERN}
            onChange={(event) =>
              void save({ lesson_pattern: event.target.value === NO_PATTERN ? null : event.target.value })
            }
            disabled={disabled}
            aria-label={`${subjectName}連堂`}
            className={`${SELECT} w-full`}
          >
            {patternOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </td>
      <td className={TD_NOWRAP}>
        <button type="button" onClick={onOpenFixed} disabled={disabled} className={BUTTON_GHOST_SM}>
          {fixedCount === 0 ? "設定" : `已固定 ${fixedCount} 堂`}
        </button>
      </td>
      <td className={TD}>
        <select
          value={requirement.required_teacher_id ?? ""}
          onChange={(event) =>
            void save({ required_teacher_id: event.target.value === "" ? null : Number(event.target.value) })
          }
          disabled={disabled}
          aria-label={`${subjectName}指定老師`}
          className={`${SELECT} w-full`}
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
          value={requirement.required_room_id ?? ""}
          onChange={(event) =>
            void save({ required_room_id: event.target.value === "" ? null : Number(event.target.value) })
          }
          disabled={disabled}
          aria-label={`${subjectName}特殊教室`}
          className={`${SELECT} w-full`}
        >
          <option value="">原班教室</option>
          {rooms.map((room) => (
            <option key={room.id} value={room.id}>
              {room.name}
            </option>
          ))}
        </select>
      </td>
    </tr>
  );
}
