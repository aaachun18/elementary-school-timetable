import { useEffect, useState, type FormEvent, type ReactElement } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import {
  create as createScheduleVersion,
  generateLessons,
  list as listScheduleVersions,
  runScheduler,
} from "../api/scheduleVersions";
import { list as listSemesters } from "../api/semesters";
import { list as listAcademicYears } from "../api/academicYears";
import { useFlashMessage } from "../hooks/useFlashMessage";
import { useResource } from "../hooks/useResource";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";
import type {
  GenerateLessonsResponse,
  RunSchedulerFailureResponse,
  RunSchedulerSuccessResponse,
} from "../types/scheduler";
import type { ApiErrorResponse } from "../types/api";

type VersionPickerMode = "select" | "create";

function formatSemesterLabel(
  semester: Semester,
  academicYearById: Map<number, number>,
): string {
  const year = academicYearById.get(semester.academic_year_id);
  return year !== undefined
    ? `${year} 學年度第 ${semester.number} 學期`
    : `學期 ID ${semester.id}`;
}

function formatVersionLabel(
  version: ScheduleVersion,
  semesterById: Map<number, Semester>,
  academicYearById: Map<number, number>,
): string {
  const semester = semesterById.get(version.semester_id);
  const semesterLabel = semester
    ? formatSemesterLabel(semester, academicYearById)
    : `學期 ID ${version.semester_id}`;
  const statusLabel = version.status === "DRAFT" ? "草稿" : "已發布";
  return `${semesterLabel} - ${statusLabel} v${version.version_number}`;
}

// Extracts the backend's raw `detail` string for the plain {detail: "..."}
// error shape every endpoint EXCEPT run-scheduler's 422 uses. Task 32
// deliberately does not translate this to Chinese -- that's a later Task's
// job (failure diagnosis component).
function extractDetailMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorResponse>(error) && error.response?.data?.detail) {
    return error.response.data.detail;
  }
  return "無法連線到伺服器,請確認後端服務是否啟動。";
}

export default function SchedulerConsole(): ReactElement {
  const versionsResource = useResource(() => listScheduleVersions(), []);
  const semesters = useResource(() => listSemesters(), []);
  const academicYears = useResource(() => listAcademicYears(), []);

  // Copied from versionsResource.data once loaded, then updated locally
  // when a new version is created -- avoids needing a "refetch" escape
  // hatch on the shared useResource hook just for this one page.
  const [versions, setVersions] = useState<ScheduleVersion[]>([]);
  useEffect(() => {
    if (versionsResource.data !== null) {
      setVersions(versionsResource.data);
    }
  }, [versionsResource.data]);

  // --- The single source of truth for "which version is being operated on"
  // (Task 32.7 redesign). This is the ONE state step 2/3 ever read from --
  // there is no separate "dropdown value" or "just-created id" living
  // anywhere else that could disagree with it. It holds the full object
  // (not just an id) so the confirmation banner never needs to re-look it
  // up and can never show a stale/mismatched label.
  const [selectedVersion, setSelectedVersion] = useState<ScheduleVersion | null>(
    null,
  );

  // Which of the two mutually-exclusive step-1 input modes is showing.
  // Only rendered/relevant while selectedVersion is null -- once a version
  // is confirmed (by either path), both forms disappear in favour of the
  // confirmation banner, so there is never a moment where "選擇既有版本"
  // and "建立新版本" are both on screen at once.
  const [pickerMode, setPickerMode] = useState<VersionPickerMode>("select");

  // "使用既有版本" mode's own temporary selection -- deliberately separate
  // from selectedVersion: picking an option in this dropdown is not yet a
  // commitment, only clicking 選擇此版本 promotes it to selectedVersion.
  const [pendingVersionId, setPendingVersionId] = useState<number | "">("");

  // "建立新版本" mode's form fields.
  const [newSemesterId, setNewSemesterId] = useState<number | "">("");
  const [newVersionNumber, setNewVersionNumber] = useState(1);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  // A short-lived confirmation that a version was just CREATED specifically
  // (as opposed to picked from the list) -- shown alongside the same
  // confirmation banner used for both paths, not instead of it, so "did I
  // just pick or create this?" has an explicit answer for a few seconds
  // without the two paths ending up looking permanently different.
  const createFlash = useFlashMessage();

  // Auto-suggest the next version_number for whichever semester is picked
  // in create mode -- max existing version_number for that semester + 1, or
  // 1 if it has none yet.
  useEffect(() => {
    if (newSemesterId === "") {
      return;
    }
    const maxExistingVersionNumber = versions
      .filter((version) => version.semester_id === newSemesterId)
      .reduce((max, version) => Math.max(max, version.version_number), 0);
    setNewVersionNumber(maxExistingVersionNumber + 1);
  }, [newSemesterId, versions]);

  // Step 2: generate-lessons.
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateResult, setGenerateResult] = useState<GenerateLessonsResponse | null>(
    null,
  );
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Step 3: run-scheduler.
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunSchedulerSuccessResponse | null>(null);
  const [runFailure, setRunFailure] = useState<RunSchedulerFailureResponse | null>(
    null,
  );
  const [runError, setRunError] = useState<string | null>(null);

  // Shared by both "a version was just confirmed" paths AND "重新選擇版本"
  // -- a previous version's step 2/3 results must never survive onto a
  // newly-selected version's screen.
  function resetDownstreamResults(): void {
    setGenerateResult(null);
    setGenerateError(null);
    setRunResult(null);
    setRunFailure(null);
    setRunError(null);
  }

  function handleConfirmExistingVersion(): void {
    if (pendingVersionId === "") {
      return;
    }
    const version = versions.find((candidate) => candidate.id === pendingVersionId);
    if (version === undefined) {
      return;
    }
    setSelectedVersion(version);
    resetDownstreamResults();
  }

  // The explicit "重新選擇版本" escape hatch (修正方向 4): the only way to
  // change which version is being operated on, once one is confirmed --
  // there is no still-editable dropdown sitting around after confirmation.
  function handleResetVersionSelection(): void {
    setSelectedVersion(null);
    setPendingVersionId("");
    setPickerMode("select");
    resetDownstreamResults();
  }

  async function handleCreateVersion(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (newSemesterId === "") {
      return;
    }
    setIsCreating(true);
    setCreateError(null);
    try {
      const created = await createScheduleVersion({
        semester_id: newSemesterId,
        version_number: newVersionNumber,
        status: "DRAFT",
      });
      setVersions((previous) => [...previous, created]);
      setSelectedVersion(created);
      resetDownstreamResults();
      createFlash.showFlash(`已建立新版本 v${created.version_number}`);
    } catch (error) {
      setCreateError(extractDetailMessage(error));
    } finally {
      setIsCreating(false);
    }
  }

  async function handleGenerateLessons(): Promise<void> {
    if (selectedVersion === null) {
      return;
    }
    setIsGenerating(true);
    setGenerateError(null);
    setGenerateResult(null);
    try {
      const result = await generateLessons(selectedVersion.id);
      setGenerateResult(result);
    } catch (error) {
      setGenerateError(extractDetailMessage(error));
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleRunScheduler(): Promise<void> {
    if (selectedVersion === null) {
      return;
    }
    setIsRunning(true);
    setRunError(null);
    setRunResult(null);
    setRunFailure(null);
    try {
      const result = await runScheduler(selectedVersion.id);
      setRunResult(result);
    } catch (error) {
      // Only run-scheduler's 422 carries the structured
      // RunSchedulerFailureResponse shape (failure_type/lesson_failures/
      // post_hoc_violations) -- every other status (404/409/500/network)
      // is the plain {detail} shape every other endpoint uses.
      if (
        axios.isAxiosError<RunSchedulerFailureResponse>(error) &&
        error.response?.status === 422
      ) {
        setRunFailure(error.response.data);
      } else {
        setRunError(extractDetailMessage(error));
      }
    } finally {
      setIsRunning(false);
    }
  }

  const isLoadingLookups =
    versionsResource.isLoading || semesters.isLoading || academicYears.isLoading;
  const lookupErrorMessage =
    versionsResource.errorMessage ?? semesters.errorMessage ?? academicYears.errorMessage;

  if (isLoadingLookups) {
    return <p>載入中…</p>;
  }
  if (lookupErrorMessage !== null) {
    return <p role="alert">{lookupErrorMessage}</p>;
  }

  const academicYearById = new Map(
    (academicYears.data ?? []).map((academicYear) => [
      academicYear.id,
      academicYear.year,
    ]),
  );
  const semesterById = new Map(
    (semesters.data ?? []).map((semester) => [semester.id, semester]),
  );

  return (
    <div>
      <h1>排課控制台</h1>

      {/* 步驟一:選擇/建立 ScheduleVersion -- 二選一,任何時刻都只有其中
          一種輸入方式在畫面上,或是已確認狀態的說明文字,三者互斥。 */}
      <section>
        <h2>步驟一:選擇排課版本</h2>

        {selectedVersion === null ? (
          <div>
            <label>
              <input
                type="radio"
                name="version-picker-mode"
                checked={pickerMode === "select"}
                onChange={() => setPickerMode("select")}
              />
              使用既有版本
            </label>
            <label style={{ marginLeft: "1.5em" }}>
              <input
                type="radio"
                name="version-picker-mode"
                checked={pickerMode === "create"}
                onChange={() => setPickerMode("create")}
              />
              建立新版本
            </label>

            {pickerMode === "select" && (
              <div>
                <label htmlFor="version-select">選擇版本</label>
                <br />
                <select
                  id="version-select"
                  value={pendingVersionId}
                  onChange={(event) =>
                    setPendingVersionId(
                      event.target.value === "" ? "" : Number(event.target.value),
                    )
                  }
                >
                  <option value="">請選擇…</option>
                  {versions.map((version) => (
                    <option key={version.id} value={version.id}>
                      {formatVersionLabel(version, semesterById, academicYearById)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={handleConfirmExistingVersion}
                  disabled={pendingVersionId === ""}
                >
                  選擇此版本
                </button>
              </div>
            )}

            {pickerMode === "create" && (
              <form onSubmit={handleCreateVersion}>
                <label htmlFor="new-version-semester">學期</label>
                <br />
                <select
                  id="new-version-semester"
                  value={newSemesterId}
                  onChange={(event) =>
                    setNewSemesterId(
                      event.target.value === "" ? "" : Number(event.target.value),
                    )
                  }
                  required
                >
                  <option value="">請選擇…</option>
                  {(semesters.data ?? []).map((semester) => (
                    <option key={semester.id} value={semester.id}>
                      {formatSemesterLabel(semester, academicYearById)}
                    </option>
                  ))}
                </select>
                <br />
                <label htmlFor="new-version-number">版本編號</label>
                <br />
                <input
                  id="new-version-number"
                  type="number"
                  min={1}
                  value={newVersionNumber}
                  onChange={(event) => setNewVersionNumber(Number(event.target.value))}
                  required
                />
                <br />
                <button type="submit" disabled={isCreating}>
                  {isCreating ? "建立中…" : "建立新版本"}
                </button>
                {createError !== null && <p role="alert">{createError}</p>}
              </form>
            )}
          </div>
        ) : (
          // 已確認狀態:不管是「選擇既有版本」還是「建立新版本」走到這裡,
          // 呈現方式完全一樣 -- 這就是修正方向 1、3 要求的「單一、明確、
          // 一致」的狀態顯示。
          <div>
            <p style={{ fontWeight: "bold" }}>
              目前操作版本:
              {formatVersionLabel(selectedVersion, semesterById, academicYearById)}
            </p>
            {createFlash.message !== null && (
              <p style={{ color: "green", fontWeight: "bold" }}>
                ✓ {createFlash.message}
              </p>
            )}
            <button type="button" onClick={handleResetVersionSelection}>
              重新選擇版本
            </button>
          </div>
        )}
      </section>

      {selectedVersion !== null && (
        <>
          {/* 步驟二:展開課程清單 */}
          <section>
            <h2>步驟二:展開課程清單</h2>
            <button type="button" onClick={handleGenerateLessons} disabled={isGenerating}>
              {isGenerating ? "展開中…" : "展開課程清單"}
            </button>
            {generateError !== null && <p role="alert">{generateError}</p>}
            {generateResult !== null && (
              <p style={{ color: "green", fontWeight: "bold" }}>
                ✓ 共 {generateResult.total_lesson_count} 堂課待排
                {generateResult.created_count > 0 && (
                  <span style={{ fontWeight: "normal" }}>
                    (本次新增 {generateResult.created_count} 筆)
                  </span>
                )}
              </p>
            )}
          </section>

          {/* 步驟三:開始自動排課 */}
          {generateResult !== null && (
            <section>
              <h2>步驟三:開始自動排課</h2>
              <button type="button" onClick={handleRunScheduler} disabled={isRunning}>
                {isRunning ? "排課中…" : "開始自動排課"}
              </button>
              {isRunning && <p>排課可能需要一點時間,請耐心等候,畫面不會當機。</p>}
              {runError !== null && <p role="alert">{runError}</p>}

              {runResult !== null && (
                <div>
                  <p style={{ color: "green", fontWeight: "bold" }}>
                    ✓ 成功排定 {runResult.scheduled_count} 堂課(回溯{" "}
                    {runResult.backtrack_count} 次)
                  </p>
                  <Link to="/timetable">查看課表</Link>
                </div>
              )}

              {runFailure !== null && (
                <div>
                  <p role="alert" style={{ color: "#b00020", fontWeight: "bold" }}>
                    ✗ 排課失敗:{runFailure.failure_type}
                  </p>
                  <p>詳細診斷功能開發中。</p>
                  <pre>{JSON.stringify(runFailure, null, 2)}</pre>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
