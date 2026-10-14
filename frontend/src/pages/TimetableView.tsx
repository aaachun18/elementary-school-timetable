import { useEffect, useRef, useState, type ReactElement } from "react";
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
import { useResource } from "../hooks/useResource";
import { useScheduleCheck } from "../hooks/useScheduleCheck";
import { useTimetableData, type EnrichedSchedule } from "../hooks/useTimetableData";
import { isCurrentUserAdmin } from "../utils/auth";
import { getViolationSentence, resolveTimeSlotLabel } from "../utils/failureDiagnostics";
import { formatVersionLabel } from "../utils/scheduleVersionFormat";
import { mergeViolationsBySentence } from "../utils/violationMerge";
import { resolveLocateTarget, type TimetableViewMode } from "../utils/violationLocate";
import type { ConstraintViolationDetail } from "../types/scheduler";
import type { TimeSlot } from "../types/timeSlot";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  BUTTON_SECONDARY_SM,
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
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(() => {
    const raw = searchParams.get("scheduleVersionId");
    const parsed = raw !== null ? Number(raw) : NaN;
    return Number.isInteger(parsed) ? parsed : null;
  });
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
    setSelectedVersionId(versionId);
    setSelectedTargetId(null);
    setHighlightedTimeSlotId(null);
    // Task 69: a new version always starts out of edit mode.
    setIsEditModeOn(false);
    adjustment.reset();
    setIsReassignPanelOpen(false);
  }

  function handleSelectViewMode(mode: TimetableViewMode): void {
    setViewMode(mode);
    // A classId is meaningless as a teacherId/roomId and vice versa --
    // switching axis always starts the target selection over.
    setSelectedTargetId(null);
    setHighlightedTimeSlotId(null);
  }

  function handleToggleEditMode(): void {
    setIsEditModeOn((previous) => !previous);
    adjustment.reset();
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

  // Clicking the selected lesson (or any lesson when none is selected)
  // toggles the selection; clicking another lesson while one is selected
  // previews swapping them.
  function handleLessonClick(lesson: EnrichedSchedule): void {
    if (selectedLesson === null || selectedLesson.scheduleId === lesson.scheduleId) {
      adjustment.toggleSelection(lesson.scheduleId);
      return;
    }
    adjustment.requestPreview({ kind: "swap", lesson: selectedLesson, other: lesson });
  }

  function handleMoveHere(timeSlot: TimeSlot): void {
    if (selectedLesson === null) {
      return;
    }
    adjustment.requestPreview({
      kind: "move",
      lesson: selectedLesson,
      targetTimeSlotId: timeSlot.id,
    });
  }

  function handleAdjustmentSaved({ adjustment: saved, result }: SavedAdjustment): void {
    timetable.reload();
    // Keep an existing 檢查衝突 result in step with what was just saved --
    // the response already carries the whole version's new check.
    if (scheduleCheck.result !== null) {
      scheduleCheck.setResult(result.check);
    }
    const movedChange = result.changes.find(
      (change) => change.schedule_id === saved.lesson.scheduleId,
    );
    setHighlightedTimeSlotId(movedChange?.new_time_slot_id ?? null);
    adjustmentFlash.showFlash(saved.kind === "move" ? "已移動並儲存" : "已對調並儲存");
  }

  // Task 70: after a reassignment the grid shows the new teacher, and an
  // existing 檢查衝突 result is re-run against the saved state.
  function handleReassignmentSaved(): void {
    timetable.reload();
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
  const timeSlotByWeekdayAndPeriod =
    timetable.data?.timeSlotByWeekdayAndPeriod ?? new Map<string, TimeSlot>();

  // The summary counts lines as the checklist shows them (merged), not raw
  // violation records.
  const checkLookups = timetable.data?.lookups ?? null;
  const checkProblemCount =
    scheduleCheck.result === null || checkLookups === null
      ? 0
      : mergeViolationsBySentence(scheduleCheck.result.violations, (violation) =>
          getViolationSentence(violation, checkLookups),
        ).length;

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
        <section ref={timetableSectionRef} className={`${SECTION} scroll-mt-4`}>
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
                    點一堂課選取它，再點「移到這裡」移動，或點另一堂課與它對調；每次異動都會先預覽。
                  </span>
                )}
              </div>
              {!isDraftSelected && (
                <p className={NOTICE}>已發布或已封存的版本不能編輯，請先複製成新草稿。</p>
              )}
              {adjustmentFlash.message !== null && (
                <p className={SUCCESS_TEXT}>✓ {adjustmentFlash.message}</p>
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

          {timetable.data !== null && selectedTargetId !== null && (
            <TimetableGrid
              periods={periods}
              schedules={schedules}
              viewMode={viewMode}
              targetId={selectedTargetId}
              timeSlotByWeekdayAndPeriod={timeSlotByWeekdayAndPeriod}
              highlightedTimeSlotId={highlightedTimeSlotId}
              edit={
                isEditing
                  ? {
                      selected: selectedLesson,
                      disabled: adjustment.phase !== "idle" || timetable.isLoading,
                      lessonById: timetable.data.lookups.lessonById ?? new Map(),
                      onLessonClick: handleLessonClick,
                      onMoveHere: handleMoveHere,
                    }
                  : null
              }
            />
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
        />
      )}
    </div>
  );
}
