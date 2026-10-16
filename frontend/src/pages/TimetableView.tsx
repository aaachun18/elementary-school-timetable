import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";
import { list as listScheduleVersions } from "../api/scheduleVersions";
import { list as listSemesters } from "../api/semesters";
import { list as listAcademicYears } from "../api/academicYears";
import { list as listClasses } from "../api/classes";
import { list as listTeachers } from "../api/teachers";
import { list as listRooms } from "../api/rooms";
import AdjustmentPreviewDialog from "../components/AdjustmentPreviewDialog";
import ConflictChecklist from "../components/ConflictChecklist";
import TeacherReassignPanel from "../components/TeacherReassignPanel";
import TimetableGrid from "../components/TimetableGrid";
import { useFlashMessage } from "../hooks/useFlashMessage";
import { useLessonAdjustment, type SavedAdjustment } from "../hooks/useLessonAdjustment";
import { useMoveCandidates } from "../hooks/useMoveCandidates";
import { useResource } from "../hooks/useResource";
import { useScheduleCheck } from "../hooks/useScheduleCheck";
import { useTimetableData, type EnrichedSchedule } from "../hooks/useTimetableData";
import { isCurrentUserAdmin } from "../utils/auth";
import { getViolationSentence, resolveTimeSlotLabel } from "../utils/failureDiagnostics";
import { blockGroupMemberIds } from "../utils/lessonBlocks";
import { lessonTargetId } from "../utils/lessonDrop";
import { buildCandidateMarks, swapMarkKey, type CandidateMark } from "../utils/moveCandidates";
import type { PeriodDisplayMap } from "../utils/periodDisplay";
import { formatVersionLabel } from "../utils/scheduleVersionFormat";
import { mergeViolationsBySentence, splitBySeverity } from "../utils/violationMerge";
import { resolveLocateTarget, type TimetableViewMode } from "../utils/violationLocate";
import type { ConstraintViolationDetail } from "../types/scheduler";
import type { TimeSlot } from "../types/timeSlot";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  BUTTON_SECONDARY_SM,
  CANDIDATE_LEGEND,
  CANDIDATE_LEGEND_BLOCKED_SWATCH,
  CANDIDATE_LEGEND_CONFLICT_SWATCH,
  CANDIDATE_LEGEND_SAFE_SWATCH,
  CANDIDATE_LEGEND_UNAVAILABLE_SWATCH,
  CARD,
  ERROR_TEXT,
  LABEL,
  LOADING_TEXT,
  MUTED_TEXT,
  NOTICE,
  PAGE,
  PAGE_TITLE,
  SECTION,
  SELECT,
  SELECTION_BAR,
  SUCCESS_TEXT,
  TAB_BUTTON,
  TAB_BUTTON_ACTIVE,
} from "../styles/ui";

// Before the timetable has loaded: no rows, so nothing to name.
const EMPTY_PERIOD_DISPLAY: PeriodDisplayMap = new Map();

const VIEW_MODES: { key: TimetableViewMode; label: string }[] = [
  { key: "class", label: "依班級" },
  { key: "teacher", label: "依教師" },
  { key: "room", label: "依教室" },
];

export default function TimetableView(): ReactElement {
  const [searchParams] = useSearchParams();

  const versionsResource = useResource(() => listScheduleVersions(), []);
  const semesters = useResource(() => listSemesters(), []);
  const academicYears = useResource(() => listAcademicYears(), []);
  const classesResource = useResource(() => listClasses(), []);
  const teachersResource = useResource(() => listTeachers(), []);
  const roomsResource = useResource(() => listRooms(), []);

  // Task 34: arriving from 排課控制台's 「查看課表」 link carries
  // ?scheduleVersionId=<id> in the URL -- a query string rather than
  // react-router's <Link state> because it survives a page reload and can
  // be bookmarked/shared, not just an in-memory navigation.
  const [requestedVersionId, setRequestedVersionId] = useState<number | null>(() => {
    const raw = searchParams.get("scheduleVersionId");
    const parsed = raw !== null ? Number(raw) : NaN;
    return Number.isInteger(parsed) ? parsed : null;
  });
  // Task 80: versions can be deleted (ARCHIVED too), so a bookmarked or
  // back-button URL may name a version that no longer exists. Once the
  // list has loaded, such an id counts as "nothing selected" -- the page
  // shows a notice and the picker instead of a failed timetable load.
  // Derived during render, not reset in an effect.
  const isRequestedVersionMissing =
    requestedVersionId !== null &&
    versionsResource.data !== null &&
    !versionsResource.data.some((version) => version.id === requestedVersionId);
  const selectedVersionId = isRequestedVersionMissing ? null : requestedVersionId;
  const [viewMode, setViewMode] = useState<TimetableViewMode>("class");
  const [selectedTargetId, setSelectedTargetId] = useState<number | null>(null);

  const timetable = useTimetableData(selectedVersionId);

  // --- Task 68: 檢查衝突 (ADMIN only; the backend would also let a TEACHER
  // check a PUBLISHED version, this is a UI scoping choice). ---
  const isAdmin = isCurrentUserAdmin();
  const scheduleCheck = useScheduleCheck(selectedVersionId);
  // The TimeSlot whose cell 「在課表中查看」 (or, Task 69, a saved move/swap)
  // marked. Cleared by any other change of what the grid shows (view,
  // target, version) and by re-checking.
  const [highlightedTimeSlotId, setHighlightedTimeSlotId] = useState<number | null>(null);
  // Bumped on every locate so the grid scrolls into view even when the
  // same line is located twice in a row.
  const [locateRequestCount, setLocateRequestCount] = useState(0);
  const timetableSectionRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (locateRequestCount > 0) {
      timetableSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [locateRequestCount]);

  // --- Task 69: 編輯模式 (ADMIN, DRAFT only) -- click a lesson, then click
  // 「移到這裡」 or another lesson; every change is previewed first. ---
  const [isEditModeOn, setIsEditModeOn] = useState(false);
  const adjustment = useLessonAdjustment(selectedVersionId);
  const adjustmentFlash = useFlashMessage(4000);
  // Task 90: why a lesson block can't go where it was dropped -- shown
  // instead of sending a request the backend would refuse (409).
  const blockedFlash = useFlashMessage(5000);

  // Task 71 fix: the cell a just-saved move/swap landed in. Separate from
  // highlightedTimeSlotId (「在課表中查看」), and only shown in edit mode;
  // cleared on leaving edit mode, switching version or view type, and when
  // the next adjustment starts.
  const [adjustedTimeSlotId, setAdjustedTimeSlotId] = useState<number | null>(null);

  // Task 84: the lesson being dragged (the grid reports it a tick after
  // dragstart and clears it when the drag ends), and a revision that goes
  // up after every saved change so cached candidate marks are refetched.
  const [dragSourceId, setDragSourceId] = useState<number | null>(null);
  const [candidateRevision, setCandidateRevision] = useState(0);

  // Task 85: the lesson whose move/swap was last previewed. The button that
  // opened the preview is usually disabled while it loads, so ConfirmDialog
  // can't return focus to it; focus goes back to this lesson instead, or to
  // the timetable section when it can't take focus (e.g. still reloading).
  const previewedLessonIdRef = useRef<number | null>(null);
  function focusLessonOrSection(id: number | null): void {
    const lessonButton =
      id === null ? null : document.querySelector<HTMLElement>(`[data-schedule-id="${id}"]`);
    lessonButton?.focus();
    if (lessonButton === null || document.activeElement !== lessonButton) {
      timetableSectionRef.current?.focus();
    }
  }
  function restoreFocusAfterPreview(): void {
    focusLessonOrSection(previewedLessonIdRef.current);
  }
  // Task 86 fix: after a SAVED move/swap the timetable reloads, which
  // disables (or re-renders) the lesson buttons right after focus returned
  // to one, dropping focus to <body>. Once the reload is done, focus goes
  // back to that lesson -- only if nothing else has taken focus meanwhile.
  const focusAfterReloadRef = useRef<number | null>(null);
  useEffect(() => {
    if (timetable.isLoading || focusAfterReloadRef.current === null) {
      return;
    }
    const id = focusAfterReloadRef.current;
    focusAfterReloadRef.current = null;
    if (document.activeElement === null || document.activeElement === document.body) {
      focusLessonOrSection(id);
    }
  }, [timetable.isLoading, timetable.data]);

  // --- Task 70: 換教師 panel (ADMIN, DRAFT only); independent of edit mode.
  const [isReassignPanelOpen, setIsReassignPanelOpen] = useState(false);

  // Esc deselects (when no dialog is open -- the dialog handles its own
  // Esc). Listening on the document so it works wherever focus is.
  const hasSelection = adjustment.selectedScheduleId !== null;
  const canClearSelection = hasSelection && adjustment.phase === "idle";
  const clearSelection = adjustment.clearSelection;
  useEffect(() => {
    if (!canClearSelection) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        clearSelection();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [canClearSelection, clearSelection]);

  function handleSelectVersion(versionId: number | null): void {
    setRequestedVersionId(versionId);
    setSelectedTargetId(null);
    setHighlightedTimeSlotId(null);
    // Task 69: a new version always starts out of edit mode.
    setIsEditModeOn(false);
    adjustment.reset();
    setAdjustedTimeSlotId(null);
    setIsReassignPanelOpen(false);
    setDragSourceId(null);
  }

  function handleSelectViewMode(mode: TimetableViewMode): void {
    setViewMode(mode);
    // A classId is meaningless as a teacherId/roomId and vice versa --
    // switching axis always starts the target selection over.
    setSelectedTargetId(null);
    setHighlightedTimeSlotId(null);
    setAdjustedTimeSlotId(null);
  }

  function handleToggleEditMode(): void {
    setIsEditModeOn((previous) => !previous);
    adjustment.reset();
    setAdjustedTimeSlotId(null);
    setDragSourceId(null);
  }

  function handleRunCheck(): void {
    setHighlightedTimeSlotId(null);
    scheduleCheck.run();
  }

  // A violation without a time slot (H7/H8, an incomplete row) only
  // switches the view; nothing is highlighted.
  function handleLocate(violation: ConstraintViolationDetail): void {
    if (timetable.data === null) {
      return;
    }
    const target = resolveLocateTarget(violation, timetable.data.lookups);
    if (target === null) {
      return;
    }
    setViewMode(target.viewMode);
    setSelectedTargetId(target.targetId);
    setHighlightedTimeSlotId(violation.time_slot_id);
    setLocateRequestCount((previous) => previous + 1);
  }

  function canLocate(violation: ConstraintViolationDetail): boolean {
    return (
      timetable.data !== null && resolveLocateTarget(violation, timetable.data.lookups) !== null
    );
  }

  const schedules = timetable.data?.schedules ?? [];
  const selectedLesson =
    schedules.find((schedule) => schedule.scheduleId === adjustment.selectedScheduleId) ?? null;

  // --- Task 84: candidate marks for the selected or dragged lesson. A drag
  // wins over the click selection. Nothing is shown outside edit mode
  // (ADMIN + DRAFT), while a preview or save is in progress, or when the
  // lesson isn't on the grid being shown (e.g. another class was picked).
  // The marks are a hint only: every drop still goes through the preview.
  const isDraftVersion =
    (versionsResource.data ?? []).find((version) => version.id === selectedVersionId)
      ?.status === "DRAFT";
  const canShowCandidates =
    isAdmin && isEditModeOn && isDraftVersion && adjustment.phase === "idle";
  const candidateSourceId = canShowCandidates
    ? (dragSourceId ?? adjustment.selectedScheduleId)
    : null;
  const candidateSource =
    schedules.find((schedule) => schedule.scheduleId === candidateSourceId) ?? null;
  const shownCandidateSourceId =
    candidateSource !== null &&
    selectedTargetId !== null &&
    lessonTargetId(candidateSource, viewMode) === selectedTargetId
      ? candidateSource.scheduleId
      : null;
  const candidateState = useMoveCandidates(
    selectedVersionId,
    shownCandidateSourceId,
    candidateRevision,
  );
  const candidateData = candidateState.status === "ready" ? candidateState.data : null;
  const timetableLookups = timetable.data?.lookups ?? null;
  const timetableSchedules = timetable.data?.schedules ?? null;
  // Computed once per response: the grid re-renders on every dragover.
  // Task 90: with the lesson's block, so the marks know where the whole
  // block lands.
  const candidateMarks = useMemo(() => {
    if (candidateData === null || timetableLookups === null || timetableSchedules === null) {
      return null;
    }
    const source = timetableSchedules.find(
      (schedule) => schedule.scheduleId === candidateData.schedule_id,
    );
    return buildCandidateMarks(
      candidateData,
      (violation) => getViolationSentence(violation, timetableLookups),
      source === undefined ? undefined : blockGroupMemberIds(timetableSchedules, source),
    );
  }, [candidateData, timetableLookups, timetableSchedules]);

  // Task 90: the blocked mark for this lesson's move / swap, when the shown
  // marks are this lesson's; null otherwise (then the request is sent and
  // the backend decides, as before).
  function blockedMarkOf(lesson: EnrichedSchedule, mark: CandidateMark | undefined): string | null {
    if (candidateData === null || candidateData.schedule_id !== lesson.scheduleId) {
      return null;
    }
    return mark?.status === "blocked" ? mark.reason : null;
  }
  function refuseIfBlockedMove(lesson: EnrichedSchedule, timeSlot: TimeSlot): boolean {
    const reason = blockedMarkOf(lesson, candidateMarks?.cells.get(timeSlot.id));
    if (reason !== null) {
      blockedFlash.showFlash(reason);
    }
    return reason !== null;
  }
  function refuseIfBlockedSwap(lesson: EnrichedSchedule, other: EnrichedSchedule): boolean {
    const reason = blockedMarkOf(
      lesson,
      candidateMarks?.swaps.get(swapMarkKey(other.timeSlotId, other.scheduleId)),
    );
    if (reason !== null) {
      blockedFlash.showFlash(reason);
    }
    return reason !== null;
  }

  // Clicking the selected lesson (or any lesson when none is selected)
  // toggles the selection; clicking another lesson while one is selected
  // previews swapping them.
  function handleLessonClick(lesson: EnrichedSchedule): void {
    setAdjustedTimeSlotId(null);
    if (selectedLesson === null || selectedLesson.scheduleId === lesson.scheduleId) {
      adjustment.toggleSelection(lesson.scheduleId);
      return;
    }
    // Task 90: another lesson of the selected block deselects it, like
    // clicking the selected lesson itself (a block can't swap with itself).
    if (blockGroupMemberIds(schedules, selectedLesson).has(lesson.scheduleId)) {
      adjustment.clearSelection();
      return;
    }
    if (refuseIfBlockedSwap(selectedLesson, lesson)) {
      return;
    }
    previewedLessonIdRef.current = selectedLesson.scheduleId;
    adjustment.requestPreview({ kind: "swap", lesson: selectedLesson, other: lesson });
  }

  function handleMoveHere(timeSlot: TimeSlot): void {
    if (selectedLesson === null) {
      return;
    }
    setAdjustedTimeSlotId(null);
    if (refuseIfBlockedMove(selectedLesson, timeSlot)) {
      return;
    }
    previewedLessonIdRef.current = selectedLesson.scheduleId;
    adjustment.requestPreview({
      kind: "move",
      lesson: selectedLesson,
      targetTimeSlotId: timeSlot.id,
    });
  }

  // Task 71: drag & drop picks the same move/swap the clicks above do, and
  // goes through the same preview -- it never saves anything by itself.
  function handleDragStartLesson(lesson: EnrichedSchedule): void {
    setAdjustedTimeSlotId(null);
    adjustment.clearSelection();
    setDragSourceId(lesson.scheduleId);
  }

  function handleDragEndLesson(): void {
    setDragSourceId(null);
  }

  function handleDropOnCell(lesson: EnrichedSchedule, timeSlot: TimeSlot): void {
    if (refuseIfBlockedMove(lesson, timeSlot)) {
      return;
    }
    previewedLessonIdRef.current = lesson.scheduleId;
    adjustment.requestPreview({ kind: "move", lesson, targetTimeSlotId: timeSlot.id });
  }

  function handleDropOnLesson(lesson: EnrichedSchedule, other: EnrichedSchedule): void {
    if (refuseIfBlockedSwap(lesson, other)) {
      return;
    }
    previewedLessonIdRef.current = lesson.scheduleId;
    adjustment.requestPreview({ kind: "swap", lesson, other });
  }

  function handleAdjustmentSaved({ adjustment: saved, result }: SavedAdjustment): void {
    focusAfterReloadRef.current = saved.lesson.scheduleId;
    timetable.reload();
    // Keep an existing 檢查衝突 result in step with what was just saved --
    // the response already carries the whole version's new check.
    if (scheduleCheck.result !== null) {
      scheduleCheck.setResult(result.check);
    }
    const movedChange = result.changes.find(
      (change) => change.schedule_id === saved.lesson.scheduleId,
    );
    setAdjustedTimeSlotId(movedChange?.new_time_slot_id ?? null);
    adjustmentFlash.showFlash(saved.kind === "move" ? "已移動並儲存" : "已對調並儲存");
    setCandidateRevision((previous) => previous + 1);
  }

  // Task 70: after a reassignment the grid shows the new teacher, and an
  // existing 檢查衝突 result is re-run against the saved state.
  function handleReassignmentSaved(): void {
    timetable.reload();
    setCandidateRevision((previous) => previous + 1);
    if (scheduleCheck.result !== null) {
      scheduleCheck.run();
    }
  }

  function handleConfirmAdjustment(): void {
    void adjustment.confirm().then((saved) => {
      if (saved !== null) {
        handleAdjustmentSaved(saved);
      }
    });
  }

  const isLoadingLookups =
    versionsResource.isLoading ||
    semesters.isLoading ||
    academicYears.isLoading ||
    classesResource.isLoading ||
    teachersResource.isLoading ||
    roomsResource.isLoading;
  const lookupErrorMessage =
    versionsResource.errorMessage ??
    semesters.errorMessage ??
    academicYears.errorMessage ??
    classesResource.errorMessage ??
    teachersResource.errorMessage ??
    roomsResource.errorMessage;

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
  const versions = versionsResource.data ?? [];
  const selectedVersion = versions.find((version) => version.id === selectedVersionId);
  const isDraftSelected = selectedVersion?.status === "DRAFT";
  // Edit mode is only ever in effect for an ADMIN on a DRAFT.
  const isEditing = isAdmin && isDraftSelected && isEditModeOn;

  const targetOptions =
    viewMode === "class"
      ? (classesResource.data ?? []).map((item) => ({ id: item.id, label: item.name }))
      : viewMode === "teacher"
        ? (teachersResource.data ?? []).map((item) => ({ id: item.id, label: item.name }))
        : (roomsResource.data ?? []).map((item) => ({ id: item.id, label: item.name }));

  // Task 35: the vertical axis now comes from the school's full, global
  // TimeSlot structure (useTimetableData's `periods`, already sorted)
  // instead of only the periods this version's own results happened to
  // use (Task 34's approach) -- so early study hall, lunch, etc. always
  // show up even when nothing is ever scheduled into them.
  const periods = timetable.data?.periods ?? [];
  const periodDisplay = timetable.data?.periodDisplay ?? EMPTY_PERIOD_DISPLAY;
  const timeSlotByWeekdayAndPeriod =
    timetable.data?.timeSlotByWeekdayAndPeriod ?? new Map<string, TimeSlot>();

  // The summary counts lines as the checklist shows them (merged), not raw
  // violation records.
  const checkLookups = timetable.data?.lookups ?? null;
  // Task 90: problems (ERROR) and warnings are counted apart; whether the
  // timetable is valid is the backend's is_valid.
  const checkCounts =
    scheduleCheck.result === null || checkLookups === null
      ? { errors: [], warnings: [] }
      : splitBySeverity(
          mergeViolationsBySentence(scheduleCheck.result.violations, (violation) =>
            getViolationSentence(violation, checkLookups),
          ),
        );
  const checkProblemCount = checkCounts.errors.length;
  const checkWarningCount = checkCounts.warnings.length;

  const selectedLessonSlotLabel =
    selectedLesson === null || checkLookups === null
      ? ""
      : resolveTimeSlotLabel(selectedLesson.timeSlotId, checkLookups);

  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>課表檢視</h1>
      {/* Task 67: only ADMIN can ever pick an ARCHIVED version here (a
          TEACHER's version list is PUBLISHED-only, enforced by the
          backend). */}
      {selectedVersion?.status === "ARCHIVED" && (
        <p className={`${NOTICE} mb-4`}>這是已封存的版本，僅供查看。</p>
      )}
      {isRequestedVersionMissing && (
        <p className={`${NOTICE} mb-4`}>指定的排課版本已不存在（可能已被刪除），請重新選擇。</p>
      )}

      <section className={SECTION}>
        <label htmlFor="timetable-version-select" className={`${LABEL} mb-1 block`}>
          選擇排課版本
        </label>
        {/* Task 43: TEACHER's GET /api/v1/schedule-versions/ already only
            ever returns PUBLISHED versions (backend/app/services/
            schedule_version.py) -- `versions` here is exactly what this
            page is allowed to offer, no extra client-side filtering
            needed. An empty list (no PUBLISHED version exists yet, for
            TEACHER; or genuinely none at all, for ADMIN) gets its own
            message instead of a dropdown with nothing but "請選擇…" in
            it. */}
        {versions.length === 0 ? (
          <p className={MUTED_TEXT}>目前沒有可查看的排課版本。</p>
        ) : (
          <select
            id="timetable-version-select"
            value={selectedVersionId ?? ""}
            onChange={(event) =>
              handleSelectVersion(event.target.value === "" ? null : Number(event.target.value))
            }
            disabled={adjustment.phase !== "idle"}
            className={SELECT}
          >
            <option value="">請選擇…</option>
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                {formatVersionLabel(version, semesterById, academicYearById)}
              </option>
            ))}
          </select>
        )}
      </section>

      {/* Task 68: 檢查衝突 -- read-only, any version status. The result
          belongs to the selected version only (useScheduleCheck drops it
          on a version change). Waits for the timetable data, whose lookups
          turn the violations into names. */}
      {isAdmin && selectedVersionId !== null && (
        <section className={SECTION} aria-label="檢查衝突">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleRunCheck}
              disabled={scheduleCheck.isChecking || timetable.isLoading || timetable.data === null}
              className={BUTTON_PRIMARY}
            >
              {scheduleCheck.isChecking
                ? "檢查中…"
                : scheduleCheck.result !== null
                  ? "重新檢查"
                  : "檢查衝突"}
            </button>
            <span className={MUTED_TEXT}>依目前儲存的課表檢查所有排課規則，不會修改任何資料。</span>
          </div>
          {scheduleCheck.errorMessage !== null && (
            <p role="alert" className={ERROR_TEXT}>
              檢查失敗：{scheduleCheck.errorMessage}
            </p>
          )}
          {scheduleCheck.result !== null && checkLookups !== null && (
            <div className={`${CARD} mt-3`} aria-live="polite">
              {checkProblemCount > 0 && (
                <p className="mb-2 text-sm font-semibold text-red-600">
                  共 {checkProblemCount} 項問題
                  {checkWarningCount > 0 && (
                    <span className="ml-2 font-normal text-amber-800">另有 {checkWarningCount} 項警告</span>
                  )}
                </p>
              )}
              {scheduleCheck.result.is_valid && checkWarningCount > 0 && (
                <p className={`${SUCCESS_TEXT} mb-2`}>
                  ✓ 沒有違反排課規則的問題，另有 {checkWarningCount} 項警告（不影響課表是否合法）
                </p>
              )}
              <ConflictChecklist
                violations={scheduleCheck.result.violations}
                lookups={checkLookups}
                emptyText="沒有發現衝突，這份課表符合所有檢查規則"
                onLocate={handleLocate}
                canLocate={canLocate}
              />
            </div>
          )}
        </section>
      )}

      {selectedVersionId !== null && (
        <section
          ref={timetableSectionRef}
          // Task 85: focusable by script only -- where focus returns after a
          // preview when the lesson itself can't take it.
          tabIndex={-1}
          aria-label="課表"
          className={`${SECTION} scroll-mt-4 focus:outline-none`}
        >
          {/* Task 69: 編輯模式 switch -- ADMIN only; offered (disabled, with
              the reason) for a locked version too, so it's clear why. */}
          {isAdmin && selectedVersion !== undefined && (
            <div className="mb-4 flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={handleToggleEditMode}
                  disabled={!isDraftSelected || adjustment.phase !== "idle"}
                  aria-pressed={isEditing}
                  className={isEditing ? BUTTON_PRIMARY : BUTTON_SECONDARY}
                >
                  {isEditing ? "結束編輯模式" : "編輯模式"}
                </button>
                {isDraftSelected && (
                  <button
                    type="button"
                    onClick={() => setIsReassignPanelOpen((previous) => !previous)}
                    aria-expanded={isReassignPanelOpen}
                    className={isReassignPanelOpen ? BUTTON_PRIMARY : BUTTON_SECONDARY}
                  >
                    {isReassignPanelOpen ? "收合換教師" : "換教師"}
                  </button>
                )}
                {isEditing && (
                  <span className={MUTED_TEXT}>
                    點一堂課選取它，再點「移到這裡」移動，或點另一堂課與它對調；也可以直接把課拖到空格（移動）或另一堂課上（對調）。每次異動都會先預覽。
                  </span>
                )}
              </div>
              {!isDraftSelected && (
                <p className={NOTICE}>已發布或已封存的版本不能編輯，請先複製成新草稿。</p>
              )}
              {adjustmentFlash.message !== null && (
                <p className={SUCCESS_TEXT}>✓ {adjustmentFlash.message}</p>
              )}
              {blockedFlash.message !== null && (
                <p role="alert" className={NOTICE}>
                  無法放在這裡：{blockedFlash.message}
                </p>
              )}
              {adjustment.previewError !== null && (
                <p role="alert" className={ERROR_TEXT}>
                  無法預覽這次異動，已取消：{adjustment.previewError}
                </p>
              )}
              {isEditing && adjustment.phase === "loadingPreview" && (
                <p className={LOADING_TEXT} aria-live="polite">
                  正在預覽異動結果…
                </p>
              )}
              {isEditing && selectedLesson !== null && adjustment.phase === "idle" && (
                <div className={SELECTION_BAR} aria-live="polite">
                  <span>
                    已選取：{selectedLesson.className} {selectedLesson.subjectName}（
                    {selectedLessonSlotLabel}）。點選「移到這裡」移動，或點選另一堂課與它對調
                  </span>
                  <button
                    type="button"
                    onClick={adjustment.clearSelection}
                    className={BUTTON_SECONDARY_SM}
                  >
                    取消
                  </button>
                </div>
              )}
            </div>
          )}

          {isAdmin && isDraftSelected && isReassignPanelOpen && timetable.data !== null && (
            <TeacherReassignPanel
              key={selectedVersionId}
              scheduleVersionId={selectedVersionId}
              timetable={timetable.data}
              disabled={timetable.isLoading}
              onSaved={handleReassignmentSaved}
            />
          )}

          <nav className="mb-4 flex gap-2">
            {VIEW_MODES.map((mode) => (
              <button
                key={mode.key}
                type="button"
                onClick={() => handleSelectViewMode(mode.key)}
                aria-pressed={viewMode === mode.key}
                className={viewMode === mode.key ? TAB_BUTTON_ACTIVE : TAB_BUTTON}
              >
                {mode.label}
              </button>
            ))}
          </nav>

          <label htmlFor="timetable-target-select" className={`${LABEL} mb-1 block`}>
            {viewMode === "class" ? "選擇班級" : viewMode === "teacher" ? "選擇教師" : "選擇教室"}
          </label>
          <select
            id="timetable-target-select"
            value={selectedTargetId ?? ""}
            onChange={(event) => {
              setSelectedTargetId(
                event.target.value === "" ? null : Number(event.target.value),
              );
              setHighlightedTimeSlotId(null);
            }}
            className={`${SELECT} mb-4`}
          >
            <option value="">請選擇…</option>
            {targetOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>

          {timetable.isLoading && <p className={LOADING_TEXT}>載入中…</p>}
          {timetable.errorMessage !== null && (
            <p role="alert" className={ERROR_TEXT}>
              {timetable.errorMessage}
            </p>
          )}

          {/* Task 84: only while marks are shown. */}
          {isEditing && candidateMarks !== null && (
            <div
              className={CANDIDATE_LEGEND}
              aria-label="候選位置圖例"
              title="淡綠：移到這裡不會新增問題（新增的警告不算）。淡紅斜紋：會新增問題，滑鼠停在格子右上角的 ✕ 可看原因，仍可放下並預覽。灰色斜紋：連堂整組放不進去，滑鼠停在 ⊘ 可看原因。灰色：非教學時段，不能放。拖曳連堂時，整組會落在的格子以綠色虛線框出。與某堂課對調的結果寫在那堂課的滑鼠提示中。"
            >
              <span className="inline-flex items-center gap-1">
                <span className={CANDIDATE_LEGEND_SAFE_SWATCH} aria-hidden="true" />
                可放
              </span>
              <span className="inline-flex items-center gap-1">
                <span className={CANDIDATE_LEGEND_CONFLICT_SWATCH} aria-hidden="true" />
                衝突
              </span>
              <span className="inline-flex items-center gap-1">
                <span className={CANDIDATE_LEGEND_UNAVAILABLE_SWATCH} aria-hidden="true" />
                非教學
              </span>
              <span className="inline-flex items-center gap-1">
                <span className={CANDIDATE_LEGEND_BLOCKED_SWATCH} aria-hidden="true" />
                不可放
              </span>
            </div>
          )}

          {timetable.data !== null && selectedTargetId !== null && (
            <TimetableGrid
              periods={periods}
              periodDisplay={periodDisplay}
              schedules={schedules}
              viewMode={viewMode}
              targetId={selectedTargetId}
              timeSlotByWeekdayAndPeriod={timeSlotByWeekdayAndPeriod}
              highlightedTimeSlotId={highlightedTimeSlotId}
              adjustedTimeSlotId={isEditing ? adjustedTimeSlotId : null}
              edit={
                isEditing
                  ? {
                      selected: selectedLesson,
                      disabled: adjustment.phase !== "idle" || timetable.isLoading,
                      lessonById: timetable.data.lookups.lessonById ?? new Map(),
                      onLessonClick: handleLessonClick,
                      onMoveHere: handleMoveHere,
                      // Starting a drag drops any click selection first.
                      onDragStartLesson: handleDragStartLesson,
                      onDragEndLesson: handleDragEndLesson,
                      onDropOnCell: handleDropOnCell,
                      onDropOnLesson: handleDropOnLesson,
                      candidateMarks,
                    }
                  : null
              }
            />
          )}
          {isEditing && shownCandidateSourceId !== null && candidateState.status === "failed" && (
            <p className={`${MUTED_TEXT} mt-2`}>目前無法顯示候選位置，仍可直接放下並預覽</p>
          )}
        </section>
      )}

      {timetable.data !== null && (
        <AdjustmentPreviewDialog
          preview={adjustment.preview}
          lookups={timetable.data.lookups}
          isSaving={adjustment.phase === "saving"}
          saveError={adjustment.saveError}
          onConfirm={handleConfirmAdjustment}
          onCancel={adjustment.closePreview}
          restoreFocusFallback={restoreFocusAfterPreview}
          schedules={schedules}
        />
      )}
    </div>
  );
}
