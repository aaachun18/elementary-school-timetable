import { useState, type ReactElement } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { list as listAcademicYears } from "../api/academicYears";
import { list as listRequirements } from "../api/classSubjectRequirements";
import { list as listClasses } from "../api/classes";
import { list as listGrades } from "../api/grades";
import { list as listRooms } from "../api/rooms";
import { copySettings, get as getRecord } from "../api/scheduleVersions";
import { listGradeTimeSlots, listTeachers as listRecordTeachers } from "../api/semesterSettings";
import { list as listSemesters } from "../api/semesters";
import { list as listSubjects } from "../api/subjects";
import { list as listTeachers } from "../api/teachers";
import { list as listTimeSlots } from "../api/timeSlots";
import AutoScheduleOutcome from "../components/AutoScheduleOutcome";
import FixedTimeSlotEditor from "../components/FixedTimeSlotEditor";
import { extractApiErrorMessage } from "../constants/errorMessages";
import { useAutoSchedule } from "../hooks/useAutoSchedule";
import { useResource } from "../hooks/useResource";
import { rememberWizardRecord } from "../utils/wizardRecord";
import { buildPeriodDisplay } from "../utils/periodDisplay";
import { summarizeSlots } from "../utils/recordSettings";
import {
  formatRecordStatus,
  hasTimetable,
  recordStatusBadgeClass,
  semesterLabelOf,
} from "../utils/scheduleVersionFormat";
import { describeLessonPattern } from "../utils/lessonPattern";
import type { Class } from "../types/class";
import type { ClassSubjectRequirement } from "../types/classSubjectRequirement";
import type { Grade } from "../types/grade";
import type { ScheduleVersion } from "../types/scheduleVersion";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  CARD,
  ERROR_TEXT,
  HELP_TEXT,
  LABEL,
  LOADING_TEXT,
  MUTED_TEXT,
  PAGE,
  PAGE_TITLE,
  SECTION,
  SECTION_TITLE,
  SELECT,
  SUCCESS_TEXT,
  TAB_BUTTON,
  TAB_BUTTON_ACTIVE,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TH,
} from "../styles/ui";

const ALL = 1000;

// v3 (items 11-12): 檢視排課設定 -- everything one 排課紀錄 was (or will be)
// scheduled with: its teachers, the grades' open slots and every class
// subject requirement, read-only. 「複製此次排課設定」 makes a new 尚未排課
// record with the same settings; a 尚未排課 record's settings are changed in
// the wizard (修改排課設定) and scheduled right here (自動排課).
export default function RecordSettings(): ReactElement {
  const params = useParams();
  const recordId = Number(params.recordId);
  const record = useResource(() => getRecord(recordId), [recordId]);

  if (record.errorMessage !== null) {
    return (
      <div className={PAGE}>
        <BackLink />
        <p role="alert" className={ERROR_TEXT}>
          {record.errorMessage}
        </p>
      </div>
    );
  }
  if (record.data === null) {
    return (
      <div className={PAGE}>
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }
  return <SettingsView key={record.data.id} record={record.data} onChanged={record.reload} />;
}

function BackLink(): ReactElement {
  return (
    <p className="mb-3">
      <Link to="/records" className={BUTTON_SECONDARY}>
        ← 返回排課紀錄
      </Link>
    </p>
  );
}

function SettingsView({ record, onChanged }: { record: ScheduleVersion; onChanged: () => void }): ReactElement {
  const navigate = useNavigate();
  const data = useResource(
    () =>
      Promise.all([
        listRecordTeachers(record.id),
        listGradeTimeSlots(record.id),
        listRequirements(0, ALL, { schedule_version_id: record.id }),
        listGrades(0, ALL),
        listClasses(0, ALL),
        listSubjects(0, ALL),
        listRooms(0, ALL),
        listTimeSlots(0, ALL),
        listSemesters(0, ALL),
        listAcademicYears(0, ALL),
        listTeachers(0, ALL),
      ]),
    [record.id],
  );
  const autoSchedule = useAutoSchedule(record.id);
  const [isCopying, setIsCopying] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const isNotScheduled = record.status === "NOT_SCHEDULED";

  async function handleCopy(): Promise<void> {
    setIsCopying(true);
    setCopyError(null);
    try {
      const created = await copySettings(record.id);
      navigate(`/records/${created.id}/settings`, {
        state: { flash: `已複製成新的排課紀錄（編號 ${created.display_number}，尚未排課），可以修改設定後自動排課。` },
      });
    } catch (caught) {
      setCopyError(extractApiErrorMessage(caught));
    } finally {
      setIsCopying(false);
    }
  }

  async function handleRun(): Promise<void> {
    // The failure diagnostics link to the wizard's steps: they open this
    // record.
    rememberWizardRecord(record.id);
    if (await autoSchedule.run()) {
      onChanged();
    }
  }

  if (data.errorMessage !== null) {
    return (
      <div className={PAGE}>
        <BackLink />
        <p role="alert" className={ERROR_TEXT}>
          {data.errorMessage}
        </p>
      </div>
    );
  }
  if (data.data === null) {
    return (
      <div className={PAGE}>
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }
  const [
    teachers,
    gradeSlots,
    requirements,
    grades,
    classes,
    subjects,
    rooms,
    timeSlots,
    semesters,
    academicYears,
    allTeachers,
  ] = data.data;
  const academicYearById = new Map(academicYears.map((item) => [item.id, item.year]));
  const semesterById = new Map(semesters.map((item) => [item.id, item]));
  const timeSlotById = new Map(timeSlots.map((item) => [item.id, item]));
  const periodDisplay = buildPeriodDisplay(timeSlots);
  const gradeById = new Map(grades.map((item) => [item.id, item]));
  const classById = new Map(classes.map((item) => [item.id, item]));
  const subjectNameById = new Map(subjects.map((item) => [item.id, item.name]));
  const roomNameById = new Map(rooms.map((item) => [item.id, item.name]));
  const teacherNameById = new Map(allTeachers.map((item) => [item.id, item.name]));
  const levelOfClass = (classId: number): number => gradeById.get(classById.get(classId)?.grade_id ?? -1)?.level ?? 0;
  const sortedRequirements = [...requirements].sort(
    (a, b) =>
      levelOfClass(a.class_id) - levelOfClass(b.class_id) ||
      a.class_id - b.class_id ||
      a.subject_id - b.subject_id,
  );
  const sortedGradeSlots = [...gradeSlots].sort(
    (a, b) => (gradeById.get(a.grade_id)?.level ?? 0) - (gradeById.get(b.grade_id)?.level ?? 0),
  );
  const lessonCount = requirements.reduce((sum, item) => sum + item.weekly_periods, 0);
  const sortedGrades = [...grades].sort((a, b) => a.level - b.level);

  return (
    <div className={PAGE}>
      <BackLink />
      <h1 className={PAGE_TITLE}>排課設定・編號 {record.display_number}</h1>
      <p className="mb-3 flex flex-wrap items-center gap-2 text-sm text-gray-700">
        {semesterLabelOf(record, semesterById, academicYearById)}
        <span className={recordStatusBadgeClass(record)}>{formatRecordStatus(record)}</span>
        {record.note !== null && <span className={MUTED_TEXT}>備註：{record.note}</span>}
      </p>
      <FlashFromNavigation />

      <section className={SECTION} aria-label="操作">
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void handleCopy()} disabled={isCopying} className={BUTTON_SECONDARY}>
            {isCopying ? "複製中…" : "複製此次排課設定"}
          </button>
          {isNotScheduled && (
            <>
              <Link to={`/wizard?record=${record.id}`} className={BUTTON_SECONDARY}>
                修改排課設定
              </Link>
              <button
                type="button"
                onClick={() => void handleRun()}
                disabled={autoSchedule.isRunning || teachers.length === 0 || requirements.length === 0}
                className={BUTTON_PRIMARY}
              >
                {autoSchedule.isRunning ? "排課中…" : "自動排課"}
              </button>
            </>
          )}
          {hasTimetable(record.status) && (
            <Link to={`/timetable?scheduleVersionId=${record.id}`} className={BUTTON_PRIMARY}>
              檢視課表
            </Link>
          )}
        </div>
        <p className={`${HELP_TEXT} mt-2`}>
          {isNotScheduled
            ? "這筆紀錄還沒排課，可以「修改排課設定」，確定後按「自動排課」。"
            : "這筆紀錄已經排過課，設定不能再修改；要用不同設定重新排課，請「複製此次排課設定」，在新的紀錄修改後自動排課。"}
        </p>
        {copyError !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {copyError}
          </p>
        )}
        <AutoScheduleOutcome versionId={record.id} state={autoSchedule} />
      </section>

      {isNotScheduled && autoSchedule.result === null && <FixedTimeSlotEditor versionId={record.id} />}

      <section className={SECTION}>
        <h2 className={SECTION_TITLE}>參與教師（{teachers.length} 位）</h2>
        {teachers.length === 0 ? (
          <p className={MUTED_TEXT}>還沒有設定參與排課的老師。</p>
        ) : (
          <div className={TABLE_WRAPPER}>
            <table className={TABLE}>
              <thead>
                <tr className={TABLE_HEAD_ROW}>
                  <th className={TH}>老師</th>
                  <th className={TH}>每週最低節數</th>
                  <th className={TH}>每週最高節數</th>
                  <th className={TH}>不可排課時段</th>
                  <th className={TH}>導師班級</th>
                </tr>
              </thead>
              <tbody>
                {teachers.map((teacher) => (
                  <tr key={teacher.teacher_id}>
                    <td className={TD}>{teacher.teacher_name}</td>
                    <td className={TD}>{teacher.min_weekly_periods}</td>
                    <td className={TD}>{teacher.max_weekly_periods}</td>
                    <td className={TD}>
                      {summarizeSlots(teacher.unavailable_time_slot_ids, timeSlotById, periodDisplay)}
                    </td>
                    <td className={TD}>
                      {teacher.homeroom_class_id === null
                        ? "—"
                        : (classById.get(teacher.homeroom_class_id)?.name ?? `班級 ${teacher.homeroom_class_id}`)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className={SECTION}>
        <h2 className={SECTION_TITLE}>年級可排節次</h2>
        {sortedGradeSlots.length === 0 ? (
          <p className={MUTED_TEXT}>還沒有設定年級可排節次（未設定的年級不受限制）。</p>
        ) : (
          <div className={CARD}>
            <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
              {sortedGradeSlots.map((item) => (
                <li key={item.grade_id}>
                  <span className="font-medium text-gray-900">{gradeById.get(item.grade_id)?.name ?? `年級 ${item.grade_id}`}</span>
                  ：{summarizeSlots(item.time_slot_ids, timeSlotById, periodDisplay)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <RequirementsSection
        requirements={sortedRequirements}
        grades={sortedGrades}
        classById={classById}
        subjectNameById={subjectNameById}
        teacherNameById={teacherNameById}
        roomNameById={roomNameById}
        lessonCount={lessonCount}
      />
    </div>
  );
}

// 科目需求, one class at a time: pick a grade, then one of its classes'
// buttons (the first one to start with) to list that class's requirements.
function RequirementsSection({
  requirements,
  grades,
  classById,
  subjectNameById,
  teacherNameById,
  roomNameById,
  lessonCount,
}: {
  requirements: readonly ClassSubjectRequirement[];
  grades: readonly Grade[];
  classById: ReadonlyMap<number, Class>;
  subjectNameById: ReadonlyMap<number, string>;
  teacherNameById: ReadonlyMap<number, string>;
  roomNameById: ReadonlyMap<number, string>;
  lessonCount: number;
}): ReactElement {
  const classIdsWithRequirements = new Set(requirements.map((item) => item.class_id));
  const classesOf = (gradeId: number | null): Class[] =>
    [...classById.values()]
      .filter((item) => item.grade_id === gradeId && classIdsWithRequirements.has(item.id))
      .sort((a, b) => a.id - b.id);
  const gradesWithRequirements = grades.filter((grade) => classesOf(grade.id).length > 0);
  const [gradeId, setGradeId] = useState<number | null>(gradesWithRequirements[0]?.id ?? null);
  const gradeClasses = classesOf(gradeId);
  const [classId, setClassId] = useState<number | null>(gradeClasses[0]?.id ?? null);

  function selectGrade(nextGradeId: number): void {
    setGradeId(nextGradeId);
    setClassId(classesOf(nextGradeId)[0]?.id ?? null);
  }

  const classRequirements = requirements.filter((item) => item.class_id === classId);

  return (
    <section className={SECTION}>
      <h2 className={SECTION_TITLE}>
        科目需求（{classIdsWithRequirements.size} 個班級，共 {lessonCount} 堂課）
      </h2>
      {requirements.length === 0 ? (
        <p className={MUTED_TEXT}>還沒有科目需求。</p>
      ) : (
        <>
          <label className="mb-3 flex items-center gap-2">
            <span className={LABEL}>年級</span>
            <select
              value={gradeId ?? ""}
              onChange={(event) => selectGrade(Number(event.target.value))}
              className={SELECT}
            >
              {gradesWithRequirements.map((grade) => (
                <option key={grade.id} value={grade.id}>
                  {grade.name}
                </option>
              ))}
            </select>
          </label>
          <nav aria-label="班級" className="mb-3 flex flex-wrap gap-1">
            {gradeClasses.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setClassId(item.id)}
                aria-current={item.id === classId ? "true" : undefined}
                className={item.id === classId ? TAB_BUTTON_ACTIVE : TAB_BUTTON}
              >
                {item.name}
              </button>
            ))}
          </nav>
          {classRequirements.length === 0 ? (
            <p className={MUTED_TEXT}>請選擇班級。</p>
          ) : (
            <div className={TABLE_WRAPPER}>
              <table className={TABLE}>
                <thead>
                  <tr className={TABLE_HEAD_ROW}>
                    <th className={TH}>科目</th>
                    <th className={TH}>每週節數</th>
                    <th className={TH}>連堂</th>
                    <th className={TH}>指定老師</th>
                    <th className={TH}>指定教室</th>
                  </tr>
                </thead>
                <tbody>
                  {classRequirements.map((requirement) => (
                    <tr key={requirement.id}>
                      <td className={TD}>{subjectNameById.get(requirement.subject_id) ?? `科目 ${requirement.subject_id}`}</td>
                      <td className={TD}>{requirement.weekly_periods}</td>
                      <td className={TD}>
                        {requirement.lesson_pattern
                          ? `${requirement.lesson_pattern}（${describeLessonPattern(requirement.lesson_pattern)}）`
                          : "不指定"}
                      </td>
                      <td className={TD}>
                        {requirement.required_teacher_id === null
                          ? "不指定"
                          : (teacherNameById.get(requirement.required_teacher_id) ?? `老師 ${requirement.required_teacher_id}`)}
                      </td>
                      <td className={TD}>
                        {requirement.required_room_id === null
                          ? "原班教室"
                          : (roomNameById.get(requirement.required_room_id) ?? `教室 ${requirement.required_room_id}`)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}

// A one-off message handed over by the page that navigated here (e.g.
// 「已複製成新的排課紀錄…」, in the navigation state).
function FlashFromNavigation(): ReactElement | null {
  const state: unknown = useLocation().state;
  const flash =
    typeof state === "object" && state !== null && "flash" in state ? (state as { flash: unknown }).flash : null;
  return typeof flash === "string" ? <p className={`${SUCCESS_TEXT} mb-3`}>✓ {flash}</p> : null;
}
