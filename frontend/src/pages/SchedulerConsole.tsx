import { useEffect, useState, type FormEvent, type ReactElement } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import {
  copy as copyScheduleVersion,
  create as createScheduleVersion,
  generateLessons,
  list as listScheduleVersions,
  publish as publishScheduleVersion,
  runScheduler,
  unpublish as unpublishScheduleVersion,
} from "../api/scheduleVersions";
import { list as listSchedules } from "../api/schedules";
import { list as listSemesters } from "../api/semesters";
import { list as listAcademicYears } from "../api/academicYears";
import { fixTimeSlot } from "../api/lessons";
import { useFlashMessage } from "../hooks/useFlashMessage";
import { useResource } from "../hooks/useResource";
import {
  useFixedTimeSlotData,
  type FixedTimeSlotGroup,
} from "../hooks/useFixedTimeSlotData";
import ConfirmDialog from "../components/ConfirmDialog";
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
  formatVersionStatus,
  versionStatusBadgeClass,
} from "../utils/scheduleVersionFormat";
import { formatTimeSlotLabel } from "../utils/timeSlotFormat";
import {
  BADGE_SUCCESS,
  BUTTON_DANGER,
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

// Task 67: which version-management ConfirmDialog is open, if any.
type VersionAction = "publish" | "unpublish" | "copy";

// Copy dialog: same semester (new DRAFT, Schedule rows only) or another
// semester of the same academic year (requirements + Lessons + rows).
type CopyTargetMode = "same" | "other";

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

  // --- 版本管理(Task 67;取代 Task 43 的單一「發布」按鈕):發布、取消
  // 發布、重新發布已封存版本、複製成新草稿。Deliberately NOT gated behind
  // this session's own runResult -- ADMIN may run the scheduler, go check
  // the timetable, and only come back to publish later (even in a later
  // visit to this page, after re-selecting an existing version). The
  // controls live next to the confirmed-version banner instead, chosen by
  // selectedVersion.status. Every action is confirmed through one
  // ConfirmDialog at a time; its error stays inside the dialog, which stays
  // open so the user can retry or change the input.
  const [openAction, setOpenAction] = useState<VersionAction | null>(null);
  const [isActionBusy, setIsActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copyTargetMode, setCopyTargetMode] = useState<CopyTargetMode>("same");
  const [copyTargetSemesterId, setCopyTargetSemesterId] = useState<number | "">("");
  // Set only when an action itself succeeded but re-fetching the version
  // list afterwards failed -- other versions' statuses may then be stale.
  const [versionsRefreshError, setVersionsRefreshError] = useState<string | null>(null);
  const versionActionFlash = useFlashMessage();

  // Task 67: a DRAFT that already has Schedule rows (e.g. one made by copy,
  // or one the scheduler already ran on) can't be auto-scheduled again --
  // the backend refuses with ScheduleVersionAlreadyScheduledError, whose
  // advice ("先刪除既有排課結果記錄") has no matching action anywhere in this
  // UI. So check up front with a 1-row filtered query and explain instead.
  // Re-checked after a successful run (runResult in deps). A failed check
  // just leaves the button enabled -- the backend still has the final say.
  const scheduleRowsCheck = useResource(
    () =>
      selectedVersion === null || selectedVersion.status !== "DRAFT"
        ? Promise.resolve(false)
        : listSchedules(0, 1, { schedule_version_id: selectedVersion.id }).then(
            (rows) => rows.length > 0,
          ),
    [selectedVersion?.id, selectedVersion?.status, runResult],
  );
  const isDraftAlreadyScheduled =
    !scheduleRowsCheck.isLoading && scheduleRowsCheck.data === true;

  // Built from whatever has loaded so far (empty until then) -- declared up
  // here, not after the loading/error early returns below, because the
  // version-action handlers use them too.
  const academicYearById = new Map(
    (academicYears.data ?? []).map((academicYear) => [
      academicYear.id,
      academicYear.year,
    ]),
  );
  const semesterById = new Map(
    (semesters.data ?? []).map((semester) => [semester.id, semester]),
  );

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
    setOpenAction(null);
    setActionError(null);
    setVersionsRefreshError(null);
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

  function openVersionAction(action: VersionAction): void {
    setActionError(null);
    setCopyTargetMode("same");
    setCopyTargetSemesterId("");
    setOpenAction(action);
  }

  function closeVersionAction(): void {
    if (isActionBusy) {
      return;
    }
    setOpenAction(null);
    setActionError(null);
  }

  // Publishing/unpublishing can change OTHER versions' status too (publish
  // archives the semester's previous PUBLISHED version), so after any
  // action the whole list is re-fetched, and the selected version is
  // re-read from it. `focus` is the version the action returned -- the one
  // to select afterwards (for copy: the new draft).
  async function refreshVersions(focus: ScheduleVersion): Promise<void> {
    setVersionsRefreshError(null);
    try {
      const latest = await listScheduleVersions();
      setVersions(latest);
      setSelectedVersion(latest.find((version) => version.id === focus.id) ?? focus);
    } catch (error) {
      setVersions((previous) =>
        previous.some((version) => version.id === focus.id)
          ? previous.map((version) => (version.id === focus.id ? focus : version))
          : [...previous, focus],
      );
      setSelectedVersion(focus);
      setVersionsRefreshError(
        `操作已完成，但重新載入版本清單失敗（${extractApiErrorMessage(error)}），其他版本的狀態可能不是最新的，請重新整理頁面。`,
      );
    }
  }

  // Shared by all three actions: on failure the dialog stays open with the
  // error inside; on success it closes, the previous step 2/3 results
  // (which belonged to the version as it was) are cleared, and the list is
  // reloaded.
  async function runVersionAction(
    action: () => Promise<ScheduleVersion>,
    successMessage: (result: ScheduleVersion) => string,
  ): Promise<void> {
    setIsActionBusy(true);
    setActionError(null);
    let result: ScheduleVersion;
    try {
      result = await action();
    } catch (error) {
      setActionError(extractApiErrorMessage(error));
      setIsActionBusy(false);
      return;
    }
    setIsActionBusy(false);
    resetDownstreamResults();
    versionActionFlash.showFlash(successMessage(result));
    await refreshVersions(result);
  }

  function handleConfirmPublish(): void {
    if (selectedVersion === null) {
      return;
    }
    const versionId = selectedVersion.id;
    void runVersionAction(
      () => publishScheduleVersion(versionId),
      () => "已發布，這個版本現在是本學期生效的課表",
    );
  }

  function handleConfirmUnpublish(): void {
    if (selectedVersion === null) {
      return;
    }
    const versionId = selectedVersion.id;
    void runVersionAction(
      () => unpublishScheduleVersion(versionId),
      () => "已取消發布，這個版本已改為已封存",
    );
  }

  function handleConfirmCopy(): void {
    if (selectedVersion === null) {
      return;
    }
    if (copyTargetMode === "other" && copyTargetSemesterId === "") {
      return;
    }
    const versionId = selectedVersion.id;
    const targetSemesterId = copyTargetMode === "same" ? null : Number(copyTargetSemesterId);
    void runVersionAction(
      () => copyScheduleVersion(versionId, targetSemesterId),
      (created) =>
        `已複製成新草稿：${formatVersionLabel(created, semesterById, academicYearById)}`,
    );
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

  const isSelectedDraft = selectedVersion !== null && selectedVersion.status === "DRAFT";

  // --- Version-management dialog content (Task 67) ---
  // The semester's currently PUBLISHED version other than this one, if any:
  // publishing this one will archive it.
  const otherPublishedVersion =
    selectedVersion === null
      ? undefined
      : versions.find(
          (version) =>
            version.semester_id === selectedVersion.semester_id &&
            version.status === "PUBLISHED" &&
            version.id !== selectedVersion.id,
        );
  // Cross-semester copy targets: the other semesters of the source's own
  // academic year (the backend refuses any other).
  const sourceSemester =
    selectedVersion === null ? undefined : semesterById.get(selectedVersion.semester_id);
  const copyTargetSemesters =
    sourceSemester === undefined
      ? []
      : (semesters.data ?? [])
          .filter(
            (semester) =>
              semester.academic_year_id === sourceSemester.academic_year_id &&
              semester.id !== sourceSemester.id,
          )
          .sort((a, b) => a.number - b.number);

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
            <p className="flex flex-wrap items-center gap-2 font-semibold text-gray-900">
              目前操作版本：
              {formatVersionLabel(selectedVersion, semesterById, academicYearById)}
              <span className={versionStatusBadgeClass(selectedVersion.status)}>
                {formatVersionStatus(selectedVersion.status)}
              </span>
            </p>
            {createFlash.message !== null && (
              <p className={`${SUCCESS_TEXT} mt-1`}>✓ {createFlash.message}</p>
            )}
            <button type="button" onClick={handleResetVersionSelection} className={`${BUTTON_SECONDARY} mt-3`}>
              重新選擇版本
            </button>

            {/* 版本管理(Task 67)-- 依狀態顯示不同動作,刻意不綁在「這次
                session 剛排課成功」上:ADMIN 排課完後可能會先去課表檢視核
                對,之後才回到這裡發布,甚至是重新選一次既有版本。 */}
            <div className="mt-4 border-t border-gray-200 pt-4">
              <div className="flex flex-wrap gap-2">
                {selectedVersion.status === "PUBLISHED" ? (
                  <button
                    type="button"
                    onClick={() => openVersionAction("unpublish")}
                    className={BUTTON_DANGER}
                  >
                    取消發布
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => openVersionAction("publish")}
                    className={BUTTON_PRIMARY}
                  >
                    {selectedVersion.status === "ARCHIVED" ? "發布（切換為生效版本）" : "發布"}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => openVersionAction("copy")}
                  className={BUTTON_SECONDARY}
                >
                  複製成新草稿
                </button>
              </div>
              <p className={`${HELP_TEXT} mt-2`}>
                {selectedVersion.status === "DRAFT" &&
                  "發布後老師就能在課表檢視看到這份課表；同學期原本生效的版本會自動改為已封存。已發布與已封存的課表內容都會鎖定，要修改請複製成新草稿。"}
                {selectedVersion.status === "PUBLISHED" &&
                  "這是本學期目前生效的課表，老師可以在課表檢視看到它。內容已鎖定；要修改請複製成新草稿，調整後再發布（發布時會自動取代這個版本）。也可以取消發布，之後隨時能再發布回來。"}
                {selectedVersion.status === "ARCHIVED" &&
                  "這是已封存的版本，內容已鎖定，老師看不到。可以重新發布，讓它切換為本學期的生效版本（目前生效的版本會自動封存），或複製成新草稿再修改。"}
              </p>
              {versionActionFlash.message !== null && (
                <p className={SUCCESS_TEXT}>✓ {versionActionFlash.message}</p>
              )}
              {versionsRefreshError !== null && (
                <p role="alert" className={ERROR_TEXT}>
                  {versionsRefreshError}
                </p>
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
              <button
                type="button"
                onClick={handleGenerateLessons}
                disabled={isGenerating || !isSelectedDraft}
                className={BUTTON_PRIMARY}
              >
                {isGenerating ? "展開中…" : "展開課程清單"}
              </button>
              {/* Task 67: steps 2 and 3 only apply to a DRAFT -- the
                  backend refuses both for a locked version anyway. */}
              {!isSelectedDraft && (
                <p className={`${MUTED_TEXT} mt-2`}>
                  {formatVersionStatus(selectedVersion.status)}
                  的版本內容已鎖定，不能展開課程清單或自動排課；要修改請先複製成新草稿。
                </p>
              )}
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
                <button
                  type="button"
                  onClick={handleRunScheduler}
                  disabled={isRunning || isDraftAlreadyScheduled}
                  className={BUTTON_PRIMARY}
                >
                  {isRunning ? "排課中…" : "開始自動排課"}
                </button>
                {isDraftAlreadyScheduled && runResult === null && (
                  <p className={`${MUTED_TEXT} mt-2`}>
                    這個草稿已有排課結果（例如由複製建立），無法重新自動排課。可以到
                    <Link
                      to={`/timetable?scheduleVersionId=${selectedVersion.id}`}
                      className="font-medium text-blue-600 hover:underline"
                    >
                      課表檢視
                    </Link>
                    查看，或建立新的草稿版本重新排課。
                  </p>
                )}
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

      {/* 版本管理確認對話框(Task 67) */}
      {selectedVersion !== null && (
        <>
          <ConfirmDialog
            open={openAction === "publish"}
            title={selectedVersion.status === "ARCHIVED" ? "重新發布這個版本？" : "發布這個版本？"}
            confirmLabel={selectedVersion.status === "ARCHIVED" ? "發布（切換為生效版本）" : "發布"}
            busy={isActionBusy}
            busyLabel="發布中…"
            onConfirm={handleConfirmPublish}
            onCancel={closeVersionAction}
          >
            <p>
              即將發布「{formatVersionLabel(selectedVersion, semesterById, academicYearById)}」。
            </p>
            {otherPublishedVersion !== undefined ? (
              <p>
                目前生效的「
                {formatVersionLabel(otherPublishedVersion, semesterById, academicYearById)}
                」會自動變成已封存，之後仍可再發布回來。
              </p>
            ) : (
              <p>發布後老師將看到這份課表。</p>
            )}
            <p>已發布的課表內容無法修改，要調整請先複製成新草稿。</p>
            {actionError !== null && (
              <p role="alert" className={ERROR_TEXT}>
                {actionError}
              </p>
            )}
          </ConfirmDialog>

          <ConfirmDialog
            open={openAction === "unpublish"}
            title="取消發布這個版本？"
            confirmLabel="取消發布"
            cancelLabel="返回"
            danger
            busy={isActionBusy}
            onConfirm={handleConfirmUnpublish}
            onCancel={closeVersionAction}
          >
            <p>
              「{formatVersionLabel(selectedVersion, semesterById, academicYearById)}
              」將改為已封存。
            </p>
            <p>
              取消後這個學期將沒有生效的課表，老師會看不到任何課表。之後可以隨時重新發布。
            </p>
            {actionError !== null && (
              <p role="alert" className={ERROR_TEXT}>
                {actionError}
              </p>
            )}
          </ConfirmDialog>

          <ConfirmDialog
            open={openAction === "copy"}
            title="複製成新草稿"
            confirmLabel="複製"
            busy={isActionBusy}
            busyLabel="複製中…"
            confirmDisabled={copyTargetMode === "other" && copyTargetSemesterId === ""}
            onConfirm={handleConfirmCopy}
            onCancel={closeVersionAction}
          >
            <p>
              來源：{formatVersionLabel(selectedVersion, semesterById, academicYearById)}
            </p>
            <fieldset className="flex flex-col gap-2" disabled={isActionBusy}>
              <legend className={`${LABEL} mb-1`}>複製到</legend>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="copy-target-mode"
                  checked={copyTargetMode === "same"}
                  onChange={() => setCopyTargetMode("same")}
                  className="accent-blue-600"
                />
                同一學期（建立新草稿）
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="copy-target-mode"
                  checked={copyTargetMode === "other"}
                  onChange={() => setCopyTargetMode("other")}
                  disabled={copyTargetSemesters.length === 0}
                  className="accent-blue-600"
                />
                同學年的其他學期
                {copyTargetSemesters.length === 0 && (
                  <span className={MUTED_TEXT}>（同學年沒有其他學期）</span>
                )}
              </label>
              {copyTargetMode === "other" && (
                <select
                  aria-label="目標學期"
                  value={copyTargetSemesterId}
                  onChange={(event) =>
                    setCopyTargetSemesterId(
                      event.target.value === "" ? "" : Number(event.target.value),
                    )
                  }
                  className={`${SELECT} ml-6 max-w-xs`}
                >
                  <option value="">請選擇學期…</option>
                  {copyTargetSemesters.map((semester) => (
                    <option key={semester.id} value={semester.id}>
                      {formatSemesterLabel(semester, academicYearById)}
                    </option>
                  ))}
                </select>
              )}
            </fieldset>
            <p className={MUTED_TEXT}>
              同一學期：只複製排課結果，排課需求與課程清單和來源共用。
              <br />
              其他學期：連同排課需求、課程清單與排課結果一起複製；目標學期必須還沒有任何排課需求。
            </p>
            <p className={MUTED_TEXT}>
              複製出的草稿已有排課結果，不能再自動排課，只能手動調整。
            </p>
            {actionError !== null && (
              <p role="alert" className={ERROR_TEXT}>
                {actionError}
              </p>
            )}
          </ConfirmDialog>
        </>
      )}
    </div>
  );
}
