import { useEffect, useId, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { list as listRequirements } from "../../api/classSubjectRequirements";
import { list as listClasses } from "../../api/classes";
import { list as listRooms } from "../../api/rooms";
import { preflight } from "../../api/scheduleVersions";
import { list as listSubjects } from "../../api/subjects";
import { list as listTeachers } from "../../api/teachers";
import { list as listTimeSlots } from "../../api/timeSlots";
import { listGradeTimeSlots, listTeachers as listSemesterTeachers } from "../../api/semesterSettings";
import AutoScheduleOutcome from "../AutoScheduleOutcome";
import ActionBar from "../ActionBar";
import CardHeader from "../CardHeader";
import DisabledReason from "../DisabledReason";
import { useAutoSchedule } from "../../hooks/useAutoSchedule";
import { useResource } from "../../hooks/useResource";
import { useTeacherNames } from "../../hooks/useTeacherAccounts";
import type { NameLookups } from "../../utils/failureDiagnostics";
import { PREFLIGHT_BLOCKED_REASON, preflightIssues, type PreflightIssue } from "../../utils/preflight";
import { autoScheduleDisabledReason } from "../../utils/disabledReason";
import { wizardStepLabel } from "../../utils/wizard";
import { forgetWizardRecord } from "../../utils/wizardRecord";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  CARD,
  ERROR_TEXT,
  LINK_TEXT,
  LOADING_TEXT,
  PREFLIGHT_PANEL,
  RULE_NOTE,
} from "../../styles/ui";

// Task 98 / v3, the wizard's last step: a summary of the 排課紀錄's settings,
// then 「自動排課」 -- its lessons generated from the requirements and the
// scheduler run on it. Success makes the record 自動排課 and links to its
// timetable; a failure leaves it 尚未排課 with the same diagnostics as
// before, so the settings can be fixed and the run tried again.
export default function RunStep({
  versionId,
  versionNumber,
  semesterLabel,
  onBack,
  onScheduled,
}: {
  versionId: number;
  versionNumber: number | null;
  semesterLabel: string | null;
  onBack: () => void;
  // Task 102: 自動排課 succeeded (the wizard's step row turns read only).
  onScheduled: () => void;
}): ReactElement {
  const teachers = useResource(() => listSemesterTeachers(versionId), [versionId]);
  const gradeSlots = useResource(() => listGradeTimeSlots(versionId), [versionId]);
  const requirements = useResource(
    () => listRequirements(0, 1000, { schedule_version_id: versionId }),
    [versionId],
  );
  // 排課前檢查 (read only): what would stop 自動排課, with the names to
  // say it.
  const check = useResource(() => preflight(versionId), [versionId]);
  const schoolTeachers = useResource(() => listTeachers(0, 1000), []);
  const classes = useResource(() => listClasses(0, 1000), []);
  const subjects = useResource(() => listSubjects(0, 1000), []);
  const rooms = useResource(() => listRooms(0, 1000), []);
  const timeSlots = useResource(() => listTimeSlots(0, 1000), []);
  const teacherNames = useTeacherNames();
  const autoSchedule = useAutoSchedule(versionId);
  const runReasonId = useId();
  // Scheduled: 開始排課 no longer resumes this record.
  const isScheduled = autoSchedule.result !== null;
  useEffect(() => {
    if (isScheduled) {
      forgetWizardRecord();
      onScheduled();
    }
  }, [isScheduled, onScheduled]);

  const loadError =
    teachers.errorMessage ??
    gradeSlots.errorMessage ??
    requirements.errorMessage ??
    check.errorMessage ??
    schoolTeachers.errorMessage ??
    classes.errorMessage ??
    subjects.errorMessage ??
    rooms.errorMessage ??
    timeSlots.errorMessage;
  if (loadError !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {loadError}
      </p>
    );
  }
  if (
    teachers.data === null ||
    gradeSlots.data === null ||
    requirements.data === null ||
    check.data === null ||
    schoolTeachers.data === null ||
    classes.data === null ||
    subjects.data === null ||
    rooms.data === null ||
    timeSlots.data === null
  ) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  const lookups: NameLookups = {
    teacherById: new Map(schoolTeachers.data.map((teacher) => [teacher.id, teacher])),
    classById: new Map(classes.data.map((item) => [item.id, item])),
    subjectById: new Map(subjects.data.map((subject) => [subject.id, subject])),
    roomById: new Map(rooms.data.map((room) => [room.id, room])),
    timeSlotById: new Map(timeSlots.data.map((slot) => [slot.id, slot])),
    requirementById: new Map(requirements.data.map((requirement) => [requirement.id, requirement])),
    teacherAccountById: teacherNames.accounts,
  };
  const issues = preflightIssues(check.data, lookups);
  const lessonCount = requirements.data.reduce((sum, item) => sum + item.weekly_periods, 0);
  const classCount = new Set(requirements.data.map((item) => item.class_id)).size;
  const isDone = autoSchedule.result !== null;
  const runDisabledReason =
    autoScheduleDisabledReason({
      isRunning: autoSchedule.isRunning,
      isDone,
      teacherCount: teachers.data.length,
      requirementCount: requirements.data.length,
    }) ?? (issues.length > 0 ? PREFLIGHT_BLOCKED_REASON : null);

  return (
    <>
      <div className={CARD}>
        <CardHeader
          title={wizardStepLabel("run")}
          info={
            <p>
              確認以下設定後按「自動排課」。成功的話，這筆排課紀錄會變成「自動排課」，之後可以在排課紀錄檢視課表、手動編輯與發布；沒有成功則維持「尚未排課」，可以修正設定後再試。
            </p>
          }
        />
        <p className={RULE_NOTE}>成功後會變成「自動排課」；失敗則維持「尚未排課」，可修正後再試</p>
        <ul className="mb-3 list-disc pl-6 text-sm text-gray-800">
          <li>排課紀錄編號 {versionNumber ?? "—"}</li>
          <li>{semesterLabel ?? "已選擇的學期"}</li>
          <li>參與排課的老師：{teachers.data.length} 位</li>
          <li>已設定可排節次的年級：{gradeSlots.data.length} 個</li>
          <li>
            {classCount} 個班級 · {requirements.data.length} 項科目需求 · 共 {lessonCount} 堂課
          </li>
        </ul>
        {teachers.data.length === 0 && (
          <p className="text-sm text-amber-800">
            還沒有納入任何老師，沒有老師就不能自動排課。
            <Link to={`/wizard?record=${versionId}&step=teachers`} className={LINK_TEXT}>
              回到教師設定
            </Link>
          </p>
        )}
        {!isDone && <PreflightIssues issues={issues} />}
        <AutoScheduleOutcome versionId={versionId} state={autoSchedule} />
      </div>
      {/* Task 98 Phase E: once scheduled, the outcome's own 檢視課表 /
          排課紀錄 are the way on -- 上一步 and the finished 自動排課 go. */}
      {!isDone && (
        <ActionBar
          start={
            <button type="button" onClick={onBack} disabled={autoSchedule.isRunning} className={BUTTON_SECONDARY}>
              上一步
            </button>
          }
          end={
            <>
              <DisabledReason id={runReasonId} reason={runDisabledReason} />
              <button
                type="button"
                onClick={() => void autoSchedule.run()}
                disabled={autoSchedule.isRunning || runDisabledReason !== null}
                title={runDisabledReason ?? undefined}
                aria-describedby={runDisabledReason !== null ? runReasonId : undefined}
                className={BUTTON_PRIMARY}
              >
                {autoSchedule.isRunning ? "排課中…" : "自動排課"}
              </button>
            </>
          }
        />
      )}
    </>
  );
}

// The problems that would stop 自動排課, each with its way back.
function PreflightIssues({ issues }: { issues: readonly PreflightIssue[] }): ReactElement | null {
  if (issues.length === 0) {
    return null;
  }
  return (
    <div className={PREFLIGHT_PANEL} role="alert">
      <p className="text-sm font-semibold text-red-700">排課前檢查發現以下問題，處理後才能自動排課：</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-800">
        {issues.map((issue) => (
          <li key={issue.text}>
            {issue.text}
            {issue.link !== null && (
              <Link to={issue.link.path} className={`${LINK_TEXT} ml-2`}>
                {issue.link.label}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
