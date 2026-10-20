import { useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import {
  create as createScheduleVersion,
  generateLessons,
  list as listScheduleVersions,
  runScheduler,
} from "../../api/scheduleVersions";
import { list as listSchedules } from "../../api/schedules";
import { list as listRequirements } from "../../api/classSubjectRequirements";
import { listGradeTimeSlots, listTeachers as listSemesterTeachers } from "../../api/semesterSettings";
import FailureDiagnostics from "../FailureDiagnostics";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import type { ScheduleVersion } from "../../types/scheduleVersion";
import type { RunSchedulerFailureResponse, RunSchedulerSuccessResponse } from "../../types/scheduler";
import { nextVersionNumber } from "../../utils/wizard";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  CARD,
  ERROR_TEXT,
  HELP_TEXT,
  LOADING_TEXT,
  MUTED_TEXT,
  SUCCESS_TEXT,
} from "../../styles/ui";

// The semester's newest DRAFT with no timetable yet (e.g. left by a failed
// run), reused instead of piling up empty records; null when there is none.
async function reusableDraft(semesterId: number): Promise<ScheduleVersion | null> {
  const drafts = (await listScheduleVersions(0, 1000))
    .filter((version) => version.semester_id === semesterId && version.status === "DRAFT")
    .sort((a, b) => b.version_number - a.version_number);
  for (const draft of drafts) {
    const rows = await listSchedules(0, 1, { schedule_version_id: draft.id });
    if (rows.length === 0) {
      return draft;
    }
  }
  return null;
}

// Task 98, the wizard's last step: a summary, then 「開始排課」 -- a new
// DRAFT record (or the semester's empty one), its lessons generated from
// the requirements, and the scheduler run. Success links to the record and
// its timetable; a failure shows the same diagnostics as before, so the
// settings can be fixed and the run tried again.
export default function RunStep({
  semesterId,
  semesterLabel,
  onBack,
}: {
  semesterId: number;
  semesterLabel: string | null;
  onBack: () => void;
}): ReactElement {
  const teachers = useResource(() => listSemesterTeachers(semesterId), [semesterId]);
  const gradeSlots = useResource(() => listGradeTimeSlots(semesterId), [semesterId]);
  const requirements = useResource(
    () => listRequirements(0, 1000, { semester_id: semesterId }),
    [semesterId],
  );
  const [isRunning, setIsRunning] = useState(false);
  const [version, setVersion] = useState<ScheduleVersion | null>(null);
  const [result, setResult] = useState<RunSchedulerSuccessResponse | null>(null);
  const [failure, setFailure] = useState<RunSchedulerFailureResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadError = teachers.errorMessage ?? gradeSlots.errorMessage ?? requirements.errorMessage;
  if (loadError !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {loadError}
      </p>
    );
  }
  if (teachers.data === null || gradeSlots.data === null || requirements.data === null) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  const lessonCount = requirements.data.reduce((sum, item) => sum + item.weekly_periods, 0);
  const classCount = new Set(requirements.data.map((item) => item.class_id)).size;

  async function handleRun(): Promise<void> {
    setIsRunning(true);
    setResult(null);
    setFailure(null);
    setError(null);
    try {
      const target =
        (await reusableDraft(semesterId)) ??
        (await createScheduleVersion({
          semester_id: semesterId,
          version_number: nextVersionNumber(await listScheduleVersions(0, 1000), semesterId),
          status: "DRAFT",
        }));
      setVersion(target);
      await generateLessons(target.id);
      setResult(await runScheduler(target.id));
    } catch (caught) {
      // Only run-scheduler's 422 carries the structured failure shape.
      if (axios.isAxiosError<RunSchedulerFailureResponse>(caught) && caught.response?.status === 422 && "failure_type" in (caught.response.data ?? {})) {
        setFailure(caught.response.data);
      } else {
        setError(extractApiErrorMessage(caught));
      }
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className={CARD}>
      <p className={HELP_TEXT}>確認以下設定後開始排課；每次排課都會留下一筆排課紀錄，之後可以檢視、手動修改與發布。</p>
      <ul className="mb-3 list-disc pl-6 text-sm text-gray-800">
        <li>{semesterLabel ?? "已選擇的學期"}</li>
        <li>參與排課的老師：{teachers.data.length} 位</li>
        <li>已設定可排節次的年級：{gradeSlots.data.length} 個</li>
        <li>
          科目需求：{classCount} 個班級、{requirements.data.length} 個科目，共 {lessonCount} 堂課
        </li>
      </ul>
      {teachers.data.length === 0 && <p className="text-sm text-amber-800">還沒有納入任何老師，請回到教師設定。</p>}
      <div className="flex gap-2">
        <button type="button" onClick={onBack} disabled={isRunning} className={BUTTON_SECONDARY}>
          上一步
        </button>
        <button
          type="button"
          onClick={() => void handleRun()}
          disabled={isRunning || requirements.data.length === 0 || teachers.data.length === 0}
          className={BUTTON_PRIMARY}
        >
          {isRunning ? "排課中…" : "開始排課"}
        </button>
      </div>
      {isRunning && <p className={`${MUTED_TEXT} mt-2`}>排課可能需要一點時間，請耐心等候。</p>}
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
      {result !== null && version !== null && (
        <div className="mt-3">
          <p className={SUCCESS_TEXT}>
            ✓ 排課完成：排定 {result.scheduled_count} 堂課（紀錄 v{version.version_number}，草稿）
          </p>
          <p className="mt-1 flex flex-wrap gap-4 text-sm">
            <Link to={`/timetable?scheduleVersionId=${version.id}`} className="font-medium text-blue-600 hover:underline">
              檢視與手動修改課表
            </Link>
            <Link to={`/records?scheduleVersionId=${version.id}`} className="font-medium text-blue-600 hover:underline">
              到排課紀錄發布
            </Link>
          </p>
        </div>
      )}
      {failure !== null && (
        <div className="mt-3">
          <p className="text-sm text-gray-700">
            這次沒有排出完整課表（不會留下部分結果）。依下面的說明修改設定後，可以再按一次「開始排課」。
          </p>
          <FailureDiagnostics response={failure} />
        </div>
      )}
    </div>
  );
}
