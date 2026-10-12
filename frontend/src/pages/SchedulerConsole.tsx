import { useEffect, useState, type FormEvent, type ReactElement } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import {
  create as createScheduleVersion,
  generateLessons,
  list as listScheduleVersions,
  runScheduler,
  update as updateScheduleVersion,
} from "../api/scheduleVersions";
import { list as listSemesters } from "../api/semesters";
import { list as listAcademicYears } from "../api/academicYears";
import { fixTimeSlot } from "../api/lessons";
import { useFlashMessage } from "../hooks/useFlashMessage";
import { useResource } from "../hooks/useResource";
import {
  useFixedTimeSlotData,
  type FixedTimeSlotGroup,
} from "../hooks/useFixedTimeSlotData";
import FailureDiagnostics from "../components/FailureDiagnostics";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type {
  GenerateLessonsResponse,
  RunSchedulerFailureResponse,
  RunSchedulerSuccessResponse,
} from "../types/scheduler";
import { extractApiErrorMessage } from "../constants/errorMessages";
import {
  formatSemesterLabel,
  formatVersionLabel,
} from "../utils/scheduleVersionFormat";
import { formatTimeSlotLabel } from "../utils/timeSlotFormat";
import {
  BADGE_SUCCESS,
  BUTTON_LINK,
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  CARD,
  ERROR_TEXT,
  HELP_TEXT,
  INPUT,
  LABEL,
  LOADING_TEXT,
  MUTED_TEXT,
  PAGE,
  PAGE_TITLE,
  SECTION,
  SECTION_TITLE,
  SELECT,
  SUCCESS_TEXT,
} from "../styles/ui";

type VersionPickerMode = "select" | "create";

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

  // --- 發布為最終確定版(Task 43 修正)。Deliberately NOT gated behind
  // this session's own runResult -- ADMIN may run the scheduler, go check
  // the timetable, and only come back to publish later (even in a later
  // visit to this page, after re-selecting an existing version from the
  // dropdown). The publish control lives next to the confirmed-version
  // banner instead, available any time selectedVersion.status is DRAFT.
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const publishFlash = useFlashMessage();

  // --- 設定固定時段(選填,Task 41): lets the user pin individual Lessons
  // (not whole requirements) to a specific TimeSlot before running the
  // scheduler. Only meaningful once generateResult !== null (Lessons must
  // exist first), but the hook itself is called unconditionally -- React
  // requires every hook call site to run every render regardless of what
  // JSX ends up using its result.
  const fixedSlotsResource = useFixedTimeSlotData(
    selectedVersion?.semester_id ?? null,
    generateResult,
  );
  // Local, mutable copy of the resource's groups -- same pattern as
  // `versions` above: seeded from the fetch, then updated optimistically
  // on each fix-time-slot PATCH so the "已固定" badge and dropdown value
  // change immediately without waiting on (or forcing) a refetch.
  const [fixedSlotGroups, setFixedSlotGroups] = useState<FixedTimeSlotGroup[]>([]);
  useEffect(() => {
    if (fixedSlotsResource.data !== null) {
      setFixedSlotGroups(fixedSlotsResource.data.groups);
    }
  }, [fixedSlotsResource.data]);
  // Collapsed by default (per spec: most scheduling runs never touch this,
  // so it shouldn't add visual weight every time).
  const [isFixedSlotsExpanded, setIsFixedSlotsExpanded] = useState(false);
  // At most one row's <select> is ever mid-save at a time (a user can only
  // change one dropdown per click) -- disables that row's <select> for the
  // duration so a second change can't race the first one's PATCH.
  const [savingLessonId, setSavingLessonId] = useState<number | null>(null);
  // Per-lesson error message, shown under that lesson's row only -- a
  // failed PATCH for one Lesson has no bearing on any other row.
  const [fixedSlotRowErrors, setFixedSlotRowErrors] = useState<Map<number, string>>(
    new Map(),
  );

  // Shared by both "a version was just confirmed" paths AND "重新選擇版本"
  // -- a previous version's step 2/3 results must never survive onto a
  // newly-selected version's screen.
  function resetDownstreamResults(): void {
    setGenerateResult(null);
    setGenerateError(null);
    setRunResult(null);
    setRunFailure(null);
    setRunError(null);
    setIsFixedSlotsExpanded(false);
    setSavingLessonId(null);
    setFixedSlotRowErrors(new Map());
    setPublishError(null);
  }

  // Updates every row across every group matching lessonId -- a plain
  // nested map, since a Lesson can only ever appear in exactly one group,
  // but there's no cheap O(1) lookup worth building for a per-row edit
  // this infrequent.
  function applyFixedTimeSlotValue(lessonId: number, value: number | null): void {
    setFixedSlotGroups((previousGroups) =>
      previousGroups.map((group) => ({
        ...group,
        lessons: group.lessons.map((lessonRow) =>
          lessonRow.lessonId === lessonId
            ? { ...lessonRow, fixedTimeSlotId: value }
            : lessonRow,
        ),
      })),
    );
  }

  async function handleFixedTimeSlotChange(
    lessonId: number,
    previousValue: number | null,
    rawValue: string,
  ): Promise<void> {
    const newValue = rawValue === "" ? null : Number(rawValue);
    if (newValue === previousValue) {
      return;
    }
    setSavingLessonId(lessonId);
    setFixedSlotRowErrors((previous) => {
      const next = new Map(previous);
      next.delete(lessonId);
      return next;
    });
    // Optimistic: apply immediately, per the "選了就生效" convention this
    // page already uses elsewhere -- reverted below if the PATCH fails.
    applyFixedTimeSlotValue(lessonId, newValue);
    try {
      await fixTimeSlot(lessonId, { time_slot_id: newValue });
    } catch (error) {
      applyFixedTimeSlotValue(lessonId, previousValue);
      setFixedSlotRowErrors((previous) => {
        const next = new Map(previous);
        next.set(lessonId, extractApiErrorMessage(error));
        return next;
      });
    } finally {
      setSavingLessonId(null);
    }
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
      setCreateError(extractApiErrorMessage(error));
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
      setGenerateError(extractApiErrorMessage(error));
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
        setRunError(extractApiErrorMessage(error));
      }
    } finally {
      setIsRunning(false);
    }
  }

  async function handlePublish(): Promise<void> {
    if (selectedVersion === null) {
      return;
    }
    // Native confirm(), same convention DataBrowser.tsx's CRUD delete uses
    // for an irreversible action -- publishing locks this version for
    // good (the backend's existing PUBLISHED rule means it can never be
    // turned back into a DRAFT, see update_schedule_version()).
    const confirmed = window.confirm(
      "發布後這個版本將無法再修改（無法改回草稿、無法重新展開課程清單或重新排課），且教師帳號將能在課表檢視看到這個版本。確定要發布為最終確定版嗎？",
    );
    if (!confirmed) {
      return;
    }
    setIsPublishing(true);
    setPublishError(null);
    try {
      const updated = await updateScheduleVersion(selectedVersion.id, {
        status: "PUBLISHED",
      });
      setSelectedVersion(updated);
      setVersions((previous) =>
        previous.map((version) => (version.id === updated.id ? updated : version)),
      );
      publishFlash.showFlash("已發布為最終確定版");
    } catch (error) {
      setPublishError(extractApiErrorMessage(error));
    } finally {
      setIsPublishing(false);
    }
  }

  const isLoadingLookups =
    versionsResource.isLoading || semesters.isLoading || academicYears.isLoading;
  const lookupErrorMessage =
    versionsResource.errorMessage ?? semesters.errorMessage ?? academicYears.errorMessage;

  if (isLoadingLookups) {
    return (
      <div className={PAGE}>
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }
  if (lookupErrorMessage !== null) {
    return (
      <div className={PAGE}>
        <p role="alert" className={ERROR_TEXT}>
          {lookupErrorMessage}
        </p>
      </div>
    );
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
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>排課控制台</h1>

      {/* 步驟一:選擇/建立 ScheduleVersion -- 二選一,任何時刻都只有其中
          一種輸入方式在畫面上,或是已確認狀態的說明文字,三者互斥。 */}
      <section className={SECTION}>
        <h2 className={SECTION_TITLE}>步驟一：選擇排課版本</h2>

        {selectedVersion === null ? (
          <div className={CARD}>
            <div className="mb-4 flex gap-6">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="radio"
                  name="version-picker-mode"
                  checked={pickerMode === "select"}
                  onChange={() => setPickerMode("select")}
                  className="accent-blue-600"
                />
                使用既有版本
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="radio"
                  name="version-picker-mode"
                  checked={pickerMode === "create"}
                  onChange={() => setPickerMode("create")}
                  className="accent-blue-600"
                />
                建立新版本
              </label>
            </div>

            {pickerMode === "select" && (
              <div className="flex flex-col gap-2">
                <label htmlFor="version-select" className={LABEL}>
                  選擇版本
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    id="version-select"
                    value={pendingVersionId}
                    onChange={(event) =>
                      setPendingVersionId(
                        event.target.value === "" ? "" : Number(event.target.value),
                      )
                    }
                    className={SELECT}
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
                    className={BUTTON_PRIMARY}
                  >
                    選擇此版本
                  </button>
                </div>
              </div>
            )}

            {pickerMode === "create" && (
              <form onSubmit={handleCreateVersion} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1">
                  <label htmlFor="new-version-semester" className={LABEL}>
                    學期
                  </label>
                  <select
                    id="new-version-semester"
                    value={newSemesterId}
                    onChange={(event) =>
                      setNewSemesterId(
                        event.target.value === "" ? "" : Number(event.target.value),
                      )
                    }
                    required
                    className={`${SELECT} max-w-xs`}
                  >
                    <option value="">請選擇…</option>
                    {(semesters.data ?? []).map((semester) => (
                      <option key={semester.id} value={semester.id}>
                        {formatSemesterLabel(semester, academicYearById)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label htmlFor="new-version-number" className={LABEL}>
                    版本編號
                  </label>
                  <input
                    id="new-version-number"
                    type="number"
                    min={1}
                    value={newVersionNumber}
                    onChange={(event) => setNewVersionNumber(Number(event.target.value))}
                    required
                    className={`${INPUT} max-w-xs`}
                  />
                </div>
                <div>
                  <button type="submit" disabled={isCreating} className={BUTTON_PRIMARY}>
                    {isCreating ? "建立中…" : "建立新版本"}
                  </button>
                </div>
                {createError !== null && (
                  <p role="alert" className={ERROR_TEXT}>
                    {createError}
                  </p>
                )}
              </form>
            )}
          </div>
        ) : (
          // 已確認狀態:不管是「選擇既有版本」還是「建立新版本」走到這裡,
          // 呈現方式完全一樣 -- 這就是修正方向 1、3 要求的「單一、明確、
          // 一致」的狀態顯示。
          <div className={CARD}>
            <p className="font-semibold text-gray-900">
              目前操作版本：
              {formatVersionLabel(selectedVersion, semesterById, academicYearById)}
            </p>
            {createFlash.message !== null && (
              <p className={`${SUCCESS_TEXT} mt-1`}>✓ {createFlash.message}</p>
            )}
            <button type="button" onClick={handleResetVersionSelection} className={`${BUTTON_SECONDARY} mt-3`}>
              重新選擇版本
            </button>

            {/* 發布為最終確定版(Task 43 修正)-- 刻意不綁在「這次 session
                剛排課成功」上:ADMIN 排課完後可能會先去課表檢視核對,之後
                才回到這個頁籤發布,甚至可能是完全不同的瀏覽階段、重新選一
                次既有版本。只要選到的版本還是 DRAFT,這裡就一定出現,不
                需要 runResult 還留著。 */}
            <div className="mt-4 border-t border-gray-200 pt-4">
              {selectedVersion.status === "PUBLISHED" ? (
                <p className={SUCCESS_TEXT}>
                  ✓ 此版本已發布為最終確定版，教師帳號可以在課表檢視看到它。
                </p>
              ) : (
                <div>
                  <button type="button" onClick={handlePublish} disabled={isPublishing} className={BUTTON_PRIMARY}>
                    {isPublishing ? "發布中…" : "發布為最終確定版"}
                  </button>
                  <p className={`${HELP_TEXT} mt-2`}>
                    發布後教師帳號才能在課表檢視看到這個版本；發布後無法再修改、
                    無法改回草稿、無法重新展開課程清單或重新排課。
                  </p>
                  {publishError !== null && (
                    <p role="alert" className={ERROR_TEXT}>
                      {publishError}
                    </p>
                  )}
                </div>
              )}
              {publishFlash.message !== null && (
                <p className={SUCCESS_TEXT}>✓ {publishFlash.message}</p>
              )}
            </div>
          </div>
        )}
      </section>

      {selectedVersion !== null && (
        <>
          {/* 步驟二:展開課程清單 */}
          <section className={SECTION}>
            <h2 className={SECTION_TITLE}>步驟二：展開課程清單</h2>
            <div className={CARD}>
              <button type="button" onClick={handleGenerateLessons} disabled={isGenerating} className={BUTTON_PRIMARY}>
                {isGenerating ? "展開中…" : "展開課程清單"}
              </button>
              {generateError !== null && (
                <p role="alert" className={ERROR_TEXT}>
                  {generateError}
                </p>
              )}
              {generateResult !== null && (
                <p className={`${SUCCESS_TEXT} mt-2`}>
                  ✓ 共 {generateResult.total_lesson_count} 堂課待排
                  {generateResult.created_count > 0 && (
                    <span className="font-normal text-gray-600">
                      {" "}
                      （本次新增 {generateResult.created_count} 筆）
                    </span>
                  )}
                </p>
              )}
            </div>
          </section>

          {/* 設定固定時段(選填,Task 41) -- 預設收合,只有在展開課程清單
              成功後才出現;不影響下面「開始自動排課」按鈕是否可按。 */}
          {generateResult !== null && (
            <section className={SECTION}>
              <button
                type="button"
                onClick={() => setIsFixedSlotsExpanded((previous) => !previous)}
                className={BUTTON_LINK}
              >
                {isFixedSlotsExpanded ? "▾" : "▸"} 設定固定時段（選填）
              </button>

              {isFixedSlotsExpanded && (
                <div className={`${CARD} mt-2`}>
                  {fixedSlotsResource.isLoading && <p className={LOADING_TEXT}>載入中…</p>}
                  {fixedSlotsResource.errorMessage !== null && (
                    <p role="alert" className={ERROR_TEXT}>
                      {fixedSlotsResource.errorMessage}
                    </p>
                  )}
                  {!fixedSlotsResource.isLoading &&
                    fixedSlotsResource.errorMessage === null &&
                    (fixedSlotGroups.length === 0 ? (
                      <p className={MUTED_TEXT}>目前沒有課程可供設定固定時段。</p>
                    ) : (
                      <div className="flex flex-col gap-4">
                        {fixedSlotGroups.map((group) => (
                          <div key={group.requirementId}>
                            <p className="mb-2 font-semibold text-gray-900">{group.label}</p>
                            <div className="ml-4 flex flex-col gap-2">
                              {group.lessons.map((lessonRow) => {
                                const selectId = `fixed-slot-${lessonRow.lessonId}`;
                                return (
                                  <div key={lessonRow.lessonId} className="flex flex-wrap items-center gap-2">
                                    <label htmlFor={selectId} className={LABEL}>
                                      第 {lessonRow.sequenceNumber} 堂
                                    </label>
                                    <select
                                      id={selectId}
                                      value={lessonRow.fixedTimeSlotId ?? ""}
                                      disabled={savingLessonId === lessonRow.lessonId}
                                      onChange={(event) =>
                                        handleFixedTimeSlotChange(
                                          lessonRow.lessonId,
                                          lessonRow.fixedTimeSlotId,
                                          event.target.value,
                                        )
                                      }
                                      className={SELECT}
                                    >
                                      <option value="">不固定（交給系統排）</option>
                                      {(fixedSlotsResource.data?.teachingTimeSlots ?? []).map(
                                        (timeSlot) => (
                                          <option key={timeSlot.id} value={timeSlot.id}>
                                            {formatTimeSlotLabel(timeSlot)}
                                          </option>
                                        ),
                                      )}
                                    </select>
                                    {lessonRow.fixedTimeSlotId !== null && (
                                      <span className={BADGE_SUCCESS}>已固定</span>
                                    )}
                                    {fixedSlotRowErrors.get(lessonRow.lessonId) !== undefined && (
                                      <p role="alert" className={`${ERROR_TEXT} w-full`}>
                                        {fixedSlotRowErrors.get(lessonRow.lessonId)}
                                      </p>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                      </div>
                    ))}
                </div>
              )}
            </section>
          )}

          {/* 步驟三:開始自動排課 */}
          {generateResult !== null && (
            <section className={SECTION}>
              <h2 className={SECTION_TITLE}>步驟三：開始自動排課</h2>
              <div className={CARD}>
                <button type="button" onClick={handleRunScheduler} disabled={isRunning} className={BUTTON_PRIMARY}>
                  {isRunning ? "排課中…" : "開始自動排課"}
                </button>
                {isRunning && <p className={`${MUTED_TEXT} mt-2`}>排課可能需要一點時間，請耐心等候，畫面不會當機。</p>}
                {runError !== null && (
                  <p role="alert" className={ERROR_TEXT}>
                    {runError}
                  </p>
                )}

                {runResult !== null && (
                  <div className="mt-2">
                    <p className={SUCCESS_TEXT}>
                      ✓ 成功排定 {runResult.scheduled_count} 堂課（回溯{" "}
                      {runResult.backtrack_count} 次）
                    </p>
                    <Link
                      to={`/timetable?scheduleVersionId=${selectedVersion.id}`}
                      className="text-sm font-medium text-blue-600 hover:underline"
                    >
                      查看課表
                    </Link>
                  </div>
                )}

                {runFailure !== null && <FailureDiagnostics response={runFailure} />}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
