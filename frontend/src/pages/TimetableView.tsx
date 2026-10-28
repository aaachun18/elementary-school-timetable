import { useEffect, useMemo, useRef, useState, type DragEvent, type ReactElement } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  copy as copyTimetable,
  list as listScheduleVersions,
  publish as publishRecord,
  remove as removeRecord,
  saveEditing,
  startEditing,
  unscheduledLessons as listUnscheduledLessons,
} from "../api/scheduleVersions";
import { list as listSemesters } from "../api/semesters";
import { list as listAcademicYears } from "../api/academicYears";
import { list as listClasses } from "../api/classes";
import { list as listTeachers } from "../api/teachers";
import { list as listRooms } from "../api/rooms";
import { list as listCombinedLessons } from "../api/combinedLessons";
import { listTeachers as listRecordTeachers } from "../api/semesterSettings";
import AdjustmentPreviewDialog from "../components/AdjustmentPreviewDialog";
import ConfirmDialog from "../components/ConfirmDialog";
import InfoPopover from "../components/InfoPopover";
import PageHeader from "../components/PageHeader";
import CheckStatusTag from "../components/CheckStatusTag";
import ConflictChecklist from "../components/ConflictChecklist";
import PlacementPreviewDialog from "../components/PlacementPreviewDialog";
import RoomChangeControls from "../components/RoomChangeControls";
import RoomChangePreviewDialog from "../components/RoomChangePreviewDialog";
import StatusBadge, { RecordStatusBadge } from "../components/StatusBadge";
import TeacherReassignPanel from "../components/TeacherReassignPanel";
import TimetableGrid from "../components/TimetableGrid";
import UnscheduledLessonsPanel from "../components/UnscheduledLessonsPanel";
import { useConfirm } from "../hooks/useConfirm";
import { CANCEL_LABEL } from "../utils/confirmText";
import { canSeeCheckTags, checkTags, isCheckListOpen } from "../utils/checkTag";
import { viewableChoices } from "../utils/choiceSelect";
import { formatTeacherName } from "../utils/teacherName";
import type { ScheduleCheckResult } from "../types/scheduler";
import { useFlashMessage } from "../hooks/useFlashMessage";
import { useLessonAdjustment, type SavedAdjustment } from "../hooks/useLessonAdjustment";
import { useMoveCandidates } from "../hooks/useMoveCandidates";
import { usePlaceCandidates } from "../hooks/usePlaceCandidates";
import { usePlacement, type SavedPlacement } from "../hooks/usePlacement";
import { useRoomChange, type SavedRoomChange } from "../hooks/useRoomChange";
import { useResource } from "../hooks/useResource";
import { useScheduleCheck } from "../hooks/useScheduleCheck";
import { useTimetableData, type EnrichedSchedule } from "../hooks/useTimetableData";
import { useUnscheduledLessons } from "../hooks/useUnscheduledLessons";
import { extractApiErrorMessage } from "../constants/errorMessages";
import { isCurrentUserCoordinator } from "../utils/auth";
import { getViolationSentence, resolveTimeSlotLabel } from "../utils/failureDiagnostics";
import { combinedForDisplay } from "../utils/combinedLessons";
import { blockGroupMemberIds } from "../utils/lessonBlocks";
import { homeroomTargetId, lessonTargetId } from "../utils/lessonDrop";
import { buildCandidateMarks, swapMarkKey, type CandidateMark } from "../utils/moveCandidates";
import type { PeriodDisplayMap } from "../utils/periodDisplay";
import { canChangeRoom } from "../utils/roomChange";
import { planAdjustmentRefresh } from "../utils/adjustmentRefresh";
import { visibleLocateSlot, type LocateMark } from "../utils/locateMark";
import {
  PLACE_REFUSAL_MESSAGES,
  buildPlaceCandidateMarks,
  buildPlacementCards,
  canChooseNoRoom,
  cardsForView,
  firstPlacedSlot,
  lessonCount,
  requiredRoomHint,
  roomForCard,
  teacherForCard,
  type PlacementCard,
} from "../utils/placement";
import {
  formatSemesterLabel,
  formatVersionLabel,
  hasTimetable,
  PUBLISH_BLOCKED_TITLE,
  publishBlockedMessage,
  semesterLabelOf,
} from "../utils/scheduleVersionFormat";
import { mergeViolationsBySentence, splitBySeverity, violationIdentityKey } from "../utils/violationMerge";
import { resolveLocateTarget, type TimetableViewMode } from "../utils/violationLocate";
import type { ConstraintViolationDetail, RoomChangeScope } from "../types/scheduler";
import type { TimeSlot } from "../types/timeSlot";
import {
  BUTTON_GHOST,
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  BUTTON_SECONDARY_SM,
  BUTTON_SUCCESS,
  CANDIDATE_LEGEND,
  CANDIDATE_LEGEND_BLOCKED_SWATCH,
  CANDIDATE_LEGEND_CONFLICT_SWATCH,
  CANDIDATE_LEGEND_SAFE_SWATCH,
  CANDIDATE_LEGEND_UNAVAILABLE_SWATCH,
  CARD,
  ERROR_TEXT,
  FIELD_PAGE,
  HOMEROOM_TAG,
  LABEL,
  LINK_TEXT,
  LOADING_TEXT,
  MUTED_TEXT,
  NOTICE,
  PAGE,
  META_TAG,
  SECTION,
  SELECT,
  SELECTION_BAR,
  SUCCESS_TEXT,
  TAB_BUTTON,
  TAB_BUTTON_ACTIVE,
  TOAST_LOADING,
  TOAST_NOTICE,
  TOAST_REGION,
  TOAST_SUCCESS,
} from "../styles/ui";

// Before the timetable has loaded: no rows, so nothing to name.
const EMPTY_PERIOD_DISPLAY: PeriodDisplayMap = new Map();

const VIEW_MODES: { key: TimetableViewMode; label: string }[] = [
  { key: "class", label: "依班級" },
  { key: "teacher", label: "依教師" },
  { key: "room", label: "依教室" },
];

// v3 (items 10, 13, 14): 檢視課表 -- one 排課紀錄's timetable, by class,
// teacher or room. For the 教學組長: 手動編輯課表 starts a working copy
// (every drag & drop, room change and -- for a copied timetable only --
// 換教師 changes the copy), 儲存課表 saves it (a 手動排課 record is saved
// over, anything else becomes a new 手動排課 record), 取消編輯 throws it
// away; 複製此課表 copies it (settings too) into a semester of the same
// academic year; 發布此課表 makes it the semester's published timetable.
// A 一般老師 picks among the published records only.
export default function TimetableView(): ReactElement {
  const [searchParams, setSearchParams] = useSearchParams();
  const { confirm, dialog: confirmDialog } = useConfirm();

  const versionsResource = useResource(() => listScheduleVersions(), []);
  const semesters = useResource(() => listSemesters(), []);
  const academicYears = useResource(() => listAcademicYears(), []);
  const classesResource = useResource(() => listClasses(), []);
  const teachersResource = useResource(() => listTeachers(), []);
  const roomsResource = useResource(() => listRooms(), []);

  // Task 34: 排課紀錄's 「檢視課表」 carries ?scheduleVersionId=<id> in the
  // URL -- a query string rather than react-router's <Link state> because
  // it survives a page reload and can be bookmarked/shared.
  const rawRequestedId = searchParams.get("scheduleVersionId");
  const parsedRequestedId = rawRequestedId !== null ? Number(rawRequestedId) : NaN;
  const requestedVersionId = Number.isInteger(parsedRequestedId) ? parsedRequestedId : null;
  function setRequestedVersionId(versionId: number | null): void {
    setSearchParams(versionId === null ? {} : { scheduleVersionId: String(versionId) });
  }
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

  // v3: 手動編輯課表's working copy (EDITING) -- while it exists every
  // request below works on it instead of the record itself.
  const [editingId, setEditingId] = useState<number | null>(null);
  const activeVersionId = editingId ?? selectedVersionId;
  // 共同排課 of the version being shown (a working copy has its own
  // lessons, so its own combined lessons): how a 合併節 reads on the grid.
  const combinedLessons = useResource(
    () => (activeVersionId === null ? Promise.resolve([]) : listCombinedLessons(activeVersionId)),
    [activeVersionId],
  );
  const recordTeachers = useResource(
    () => (selectedVersionId === null ? Promise.resolve([]) : listRecordTeachers(selectedVersionId)),
    [selectedVersionId],
  );
  const [recordAction, setRecordAction] = useState<"publish" | "copy" | null>(null);
  // Task 99: 發布此課表 found lessons not yet in the timetable -- the
  // warning's line, or null.
  const [publishBlocked, setPublishBlocked] = useState<string | null>(null);
  const [isRecordBusy, setIsRecordBusy] = useState(false);
  const [recordError, setRecordError] = useState<string | null>(null);
  const [copyTargetSemesterId, setCopyTargetSemesterId] = useState<number | null>(null);
  const recordFlash = useFlashMessage(6000);

  const timetable = useTimetableData(activeVersionId);

  // --- Task 68: 檢查衝突. Task 100: GET /check is 教學組長 only (a
  // TEACHER gets 403 for every record), so a teacher never calls it. ---
  // Task 98: "isAdmin" here means whoever may edit scheduling data -- a
  // 教學組長 (backend require_coordinator).
  const isAdmin = isCurrentUserCoordinator();
  const canCheck = canSeeCheckTags(isAdmin);
  const scheduleCheck = useScheduleCheck(activeVersionId);
  // The cell 「在課表中查看」 marked (amber), with where it was made. Task
  // 100: shown only while that record / mode / grid is still the one on
  // screen and the problem is not known to be gone (utils/locateMark.ts);
  // also cleared outright on saving, switching record or view, and
  // leaving edit mode.
  const [locateMark, setLocateMark] = useState<LocateMark | null>(null);
  // Bumped on every locate so the grid scrolls into view even when the
  // same line is located twice in a row.
  const [locateRequestCount, setLocateRequestCount] = useState(0);
  const timetableSectionRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (locateRequestCount > 0) {
      timetableSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [locateRequestCount]);

  // --- Task 69: 編輯 (v3: in the working copy) -- click a lesson, then
  // click 「移到這裡」 or another lesson; every change is previewed first. ---
  const isEditModeOn = isAdmin && editingId !== null;
  // 檢查衝突 runs by itself whenever the record on screen changes -- Task
  // 100: in the view mode too (a published, archived or any other record),
  // and as soon as a working copy is open; every saved change re-runs it
  // (refreshAfterAdjustment).
  const runScheduleCheck = scheduleCheck.run;
  useEffect(() => {
    if (canCheck && activeVersionId !== null) {
      runScheduleCheck();
    }
  }, [canCheck, activeVersionId, runScheduleCheck]);
  const adjustment = useLessonAdjustment(activeVersionId);
  const adjustmentFlash = useFlashMessage(4000);
  // Task 90: why a lesson block can't go where it was dropped -- shown
  // instead of sending a request the backend would refuse (409).
  const blockedFlash = useFlashMessage(5000);

  // Task 71 fix: the cell a just-saved move/swap landed in. Separate from
  // locateMark (「在課表中查看」), and only shown in edit mode;
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

  // --- Task 70: 換教師 panel -- v3: only while editing a copied timetable.
  const [isReassignPanelOpen, setIsReassignPanelOpen] = useState(false);
  // Task 99: a click on the check tag opens / closes the list -- for that
  // result only; the next result opens it again by itself if needed.
  const [checkListToggle, setCheckListToggle] = useState<{
    result: ScheduleCheckResult | null;
    open: boolean;
  } | null>(null);

  // --- Task 93: 「未排入課程」 -- lessons of the record with no row in its
  // timetable, placed by dragging a card onto a cell or clicking it and
  // then a cell's 「放到這裡」. Only while editing; nothing is fetched
  // otherwise. ---
  const isPlacementActive = isEditModeOn;
  const unscheduled = useUnscheduledLessons(isPlacementActive ? activeVersionId : null);
  const placementCards = useMemo(() => buildPlacementCards(unscheduled.lessons), [unscheduled.lessons]);
  const placement = usePlacement(activeVersionId);
  const [selectedCardKey, setSelectedCardKey] = useState<string | null>(null);
  const [draggingCardKey, setDraggingCardKey] = useState<string | null>(null);
  const [chosenTeacherByCard, setChosenTeacherByCard] = useState<ReadonlyMap<string, number>>(() => new Map());
  const [chosenRoomByCard, setChosenRoomByCard] = useState<ReadonlyMap<string, number | null>>(() => new Map());
  const [showAllClasses, setShowAllClasses] = useState(false);
  // A short hint instead of a request (no teacher yet, a refused cell).
  const placeHintFlash = useFlashMessage(5000);
  const selectedCard = placementCards.find((card) => card.key === selectedCardKey) ?? null;
  const draggingCard = placementCards.find((card) => card.key === draggingCardKey) ?? null;
  // A drag wins over the click selection, as for lessons.
  const placingCard = isPlacementActive ? (draggingCard ?? selectedCard) : null;
  // --- Task 95: 「更改教室」 of the selected scheduled lesson. ---
  const roomChange = useRoomChange(activeVersionId);
  const isBusy = adjustment.phase !== "idle" || placement.phase !== "idle" || roomChange.phase !== "idle";

  function resetPlacement(): void {
    placement.reset();
    roomChange.reset();
    setSelectedCardKey(null);
    setDraggingCardKey(null);
  }

  // Esc deselects (when no dialog is open -- the dialog handles its own
  // Esc). Listening on the document so it works wherever focus is.
  const hasSelection = adjustment.selectedScheduleId !== null || selectedCardKey !== null;
  const canClearSelection = hasSelection && adjustment.phase === "idle" && placement.phase === "idle";
  const clearSelection = adjustment.clearSelection;
  useEffect(() => {
    if (!canClearSelection) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        clearSelection();
        setSelectedCardKey(null);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [canClearSelection, clearSelection]);

  // Leaving the working copy (saved or thrown away), or switching record:
  // everything tied to what was on screen starts over.
  function resetEditingState(): void {
    setEditingId(null);
    setLocateMark(null);
    adjustment.reset();
    setAdjustedTimeSlotId(null);
    setIsReassignPanelOpen(false);
    setDragSourceId(null);
    resetPlacement();
    setChosenTeacherByCard(new Map());
    setChosenRoomByCard(new Map());
  }

  function handleSelectVersion(versionId: number | null): void {
    setRequestedVersionId(versionId);
    setSelectedTargetId(null);
    resetEditingState();
  }

  function handleSelectViewMode(mode: TimetableViewMode): void {
    setViewMode(mode);
    // A classId is meaningless as a teacherId/roomId and vice versa --
    // switching axis always starts the target selection over.
    setSelectedTargetId(null);
    setLocateMark(null);
    setAdjustedTimeSlotId(null);
  }

  // --- v3: 手動編輯課表 / 儲存課表 / 取消編輯 ---

  async function handleStartEditing(): Promise<void> {
    if (selectedVersionId === null) {
      return;
    }
    setIsRecordBusy(true);
    setRecordError(null);
    try {
      const workingCopy = await startEditing(selectedVersionId);
      resetEditingState();
      setEditingId(workingCopy.id);
    } catch (caught) {
      setRecordError(extractApiErrorMessage(caught));
    } finally {
      setIsRecordBusy(false);
    }
  }

  async function handleSaveEditing(): Promise<void> {
    if (editingId === null) {
      return;
    }
    setIsRecordBusy(true);
    setRecordError(null);
    try {
      const saved = await saveEditing(editingId);
      resetEditingState();
      versionsResource.reload();
      setRequestedVersionId(saved.id);
      recordFlash.showFlash(
        saved.id === selectedVersionId
          ? `已儲存課表（編號 ${saved.display_number}，手動排課）`
          : `已儲存為新的排課紀錄：編號 ${saved.display_number}（手動排課），原本的紀錄沒有改變`,
      );
    } catch (caught) {
      setRecordError(extractApiErrorMessage(caught));
    } finally {
      setIsRecordBusy(false);
    }
  }

  async function handleCancelEditing(): Promise<void> {
    if (editingId === null) {
      return;
    }
    const confirmed = await confirm({
      title: "放棄這次的修改？",
      message: "這次手動編輯的變更都不會儲存，課表會維持編輯前的樣子。",
      confirmLabel: "放棄修改",
      cancelLabel: CANCEL_LABEL,
      tone: "danger",
    });
    if (!confirmed) {
      return;
    }
    setIsRecordBusy(true);
    setRecordError(null);
    try {
      await removeRecord(editingId);
      resetEditingState();
    } catch (caught) {
      setRecordError(extractApiErrorMessage(caught));
    } finally {
      setIsRecordBusy(false);
    }
  }

  // --- v3: 發布此課表 / 複製此課表 ---

  function openRecordAction(action: "publish" | "copy"): void {
    setRecordError(null);
    setCopyTargetSemesterId(selectedVersion?.semester_id ?? null);
    setRecordAction(action);
  }

  // Task 99: before the publish confirmation, the record's unscheduled
  // lessons are read; while there are any, only a warning opens.
  async function handleStartPublish(): Promise<void> {
    if (selectedVersionId === null) {
      return;
    }
    setIsRecordBusy(true);
    setRecordError(null);
    try {
      const result = await listUnscheduledLessons(selectedVersionId);
      const blocked = publishBlockedMessage(result.lessons.length);
      if (blocked === null) {
        openRecordAction("publish");
      } else {
        setPublishBlocked(blocked);
      }
    } catch (caught) {
      setRecordError(extractApiErrorMessage(caught));
    } finally {
      setIsRecordBusy(false);
    }
  }

  async function handleConfirmPublish(): Promise<void> {
    if (selectedVersionId === null) {
      return;
    }
    setIsRecordBusy(true);
    setRecordError(null);
    try {
      const published = await publishRecord(selectedVersionId);
      versionsResource.reload();
      setRecordAction(null);
      recordFlash.showFlash(`已發布編號 ${published.display_number}，老師現在看得到這份課表`);
    } catch (caught) {
      setRecordError(extractApiErrorMessage(caught));
    } finally {
      setIsRecordBusy(false);
    }
  }

  async function handleConfirmCopy(): Promise<void> {
    if (selectedVersionId === null) {
      return;
    }
    setIsRecordBusy(true);
    setRecordError(null);
    try {
      const created = await copyTimetable(selectedVersionId, copyTargetSemesterId);
      versionsResource.reload();
      setRecordAction(null);
      setRequestedVersionId(created.id);
      setSelectedTargetId(null);
      resetEditingState();
      recordFlash.showFlash(
        `已複製成新的排課紀錄：編號 ${created.display_number}（複製自編號 ${created.copied_from_display_number}），現在檢視的是這份複製的課表`,
      );
    } catch (caught) {
      setRecordError(extractApiErrorMessage(caught));
    } finally {
      setIsRecordBusy(false);
    }
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
    setLocateMark(
      violation.time_slot_id === null || activeVersionId === null
        ? null
        : {
            timeSlotId: violation.time_slot_id,
            problemKey: violationIdentityKey(violation),
            versionId: activeVersionId,
            isEditing: isEditModeOn,
            viewMode: target.viewMode,
            targetId: target.targetId,
          },
    );
    setLocateRequestCount((previous) => previous + 1);
  }

  function canLocate(violation: ConstraintViolationDetail): boolean {
    return (
      timetable.data !== null && resolveLocateTarget(violation, timetable.data.lookups) !== null
    );
  }

  const schedules = timetable.data?.schedules ?? [];
  const displaySchedules = combinedForDisplay(schedules, combinedLessons.data ?? [], viewMode);
  const selectedLesson =
    schedules.find((schedule) => schedule.scheduleId === adjustment.selectedScheduleId) ?? null;

  // --- Task 84: candidate marks for the selected or dragged lesson. A drag
  // wins over the click selection. Nothing is shown outside edit mode
  // (a working copy), while a preview or save is in progress, or when the
  // lesson isn't on the grid being shown (e.g. another class was picked).
  // The marks are a hint only: every drop still goes through the preview.
  const canShowCandidates = isEditModeOn && !isBusy;
  const candidateSourceId =
    canShowCandidates && placingCard === null ? (dragSourceId ?? adjustment.selectedScheduleId) : null;
  const candidateSource =
    schedules.find((schedule) => schedule.scheduleId === candidateSourceId) ?? null;
  const shownCandidateSourceId =
    candidateSource !== null &&
    selectedTargetId !== null &&
    lessonTargetId(candidateSource, viewMode) === selectedTargetId
      ? candidateSource.scheduleId
      : null;
  const candidateState = useMoveCandidates(
    activeVersionId,
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

  // Task 93: the placing card's candidates, with its teacher and room (no
  // teacher picked yet: nothing is fetched).
  const placingTeacherId = placingCard === null ? null : teacherForCard(placingCard, chosenTeacherByCard);
  const placingRoomId = placingCard === null ? null : roomForCard(placingCard, chosenRoomByCard);
  const placeCandidateState = usePlaceCandidates(
    activeVersionId,
    canShowCandidates && placingCard !== null ? placingCard.anchorLessonId : null,
    placingTeacherId,
    placingRoomId,
    candidateRevision,
  );
  const placeCandidateData = placeCandidateState.status === "ready" ? placeCandidateState.data : null;
  const placeMarks = useMemo(
    () =>
      placeCandidateData === null || timetableLookups === null
        ? null
        : buildPlaceCandidateMarks(placeCandidateData, (violation) =>
            getViolationSentence(violation, timetableLookups),
          ),
    [placeCandidateData, timetableLookups],
  );
  const shownMarks = placingCard !== null ? placeMarks : candidateMarks;

  // Task 90: the blocked mark for this lesson's move / swap, when the shown
  // marks are this lesson's; null otherwise (then the request is sent and
  // the backend decides, as before).
  function blockedMarkOf(lesson: EnrichedSchedule, mark: CandidateMark | undefined): string | null {
    if (candidateData === null || candidateData.schedule_id !== lesson.scheduleId) {
      return null;
    }
    return mark?.status === "blocked" ? mark.reason : null;
  }
  // Task 103: `notify` false for a drop -- the cell under the pointer
  // already showed why while dragging, and no notice follows the drop.
  function refuseIfBlockedMove(lesson: EnrichedSchedule, timeSlot: TimeSlot, notify = true): boolean {
    const reason = blockedMarkOf(lesson, candidateMarks?.cells.get(timeSlot.id));
    if (reason !== null && notify) {
      blockedFlash.showFlash(reason);
    }
    return reason !== null;
  }
  function refuseIfBlockedSwap(lesson: EnrichedSchedule, other: EnrichedSchedule, notify = true): boolean {
    const reason = blockedMarkOf(
      lesson,
      candidateMarks?.swaps.get(swapMarkKey(other.timeSlotId, other.scheduleId)),
    );
    if (reason !== null && notify) {
      blockedFlash.showFlash(reason);
    }
    return reason !== null;
  }

  // Clicking the selected lesson (or any lesson when none is selected)
  // toggles the selection; clicking another lesson while one is selected
  // previews swapping them.
  function handleLessonClick(lesson: EnrichedSchedule): void {
    setAdjustedTimeSlotId(null);
    setSelectedCardKey(null);
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
    setSelectedCardKey(null);
    setDragSourceId(lesson.scheduleId);
  }

  function handleDragEndLesson(): void {
    setDragSourceId(null);
  }

  function handleDropOnCell(lesson: EnrichedSchedule, timeSlot: TimeSlot): void {
    if (refuseIfBlockedMove(lesson, timeSlot, false)) {
      return;
    }
    previewedLessonIdRef.current = lesson.scheduleId;
    adjustment.requestPreview({ kind: "move", lesson, targetTimeSlotId: timeSlot.id });
  }

  function handleDropOnLesson(lesson: EnrichedSchedule, other: EnrichedSchedule): void {
    if (refuseIfBlockedSwap(lesson, other, false)) {
      return;
    }
    previewedLessonIdRef.current = lesson.scheduleId;
    adjustment.requestPreview({ kind: "swap", lesson, other });
  }

  // Task 96: after ANY saved adjustment (move, swap, 換教師, placing, room
  // change) -- what to refresh is decided once, in planAdjustmentRefresh():
  // the timetable, the unscheduled panel in edit mode, and 檢查衝突 again
  // (always on while editing). The old result
  // stays visible until the new one arrives (useScheduleCheck.run() never
  // clears it first), so nothing flashes.
  function refreshAfterAdjustment(): void {
    const plan = planAdjustmentRefresh({
      isAdmin,
      versionStatus: isEditModeOn ? "EDITING" : null,
      isEditModeOn,
    });
    if (plan.reloadTimetable) {
      timetable.reload();
    }
    if (plan.reloadUnscheduled) {
      unscheduled.reload();
    }
    if (plan.rerunCheck) {
      scheduleCheck.run();
    }
    setCandidateRevision((previous) => previous + 1);
  }

  function handleAdjustmentSaved({ adjustment: saved, result }: SavedAdjustment): void {
    focusAfterReloadRef.current = saved.lesson.scheduleId;
    refreshAfterAdjustment();
    const movedChange = result.changes.find(
      (change) => change.schedule_id === saved.lesson.scheduleId,
    );
    setAdjustedTimeSlotId(movedChange?.new_time_slot_id ?? null);
    adjustmentFlash.showFlash(saved.kind === "move" ? "已移動並儲存" : "已對調並儲存");
  }

  // Task 70: after a reassignment the grid shows the new teacher.
  function handleReassignmentSaved(): void {
    refreshAfterAdjustment();
  }

  // --- Task 93: placing a card ---

  function handleCardClick(card: PlacementCard): void {
    if (teacherForCard(card, chosenTeacherByCard) === null) {
      placeHintFlash.showFlash(PLACE_REFUSAL_MESSAGES.TEACHER_REQUIRED);
      return;
    }
    setAdjustedTimeSlotId(null);
    adjustment.clearSelection();
    setSelectedCardKey((previous) => (previous === card.key ? null : card.key));
  }

  function handleCardDragStart(card: PlacementCard, event: DragEvent<HTMLButtonElement>): void {
    if (isBusy || teacherForCard(card, chosenTeacherByCard) === null) {
      event.preventDefault();
      if (!isBusy) {
        placeHintFlash.showFlash(PLACE_REFUSAL_MESSAGES.TEACHER_REQUIRED);
      }
      return;
    }
    event.dataTransfer.setData("text/plain", `place:${card.key}`);
    event.dataTransfer.effectAllowed = "move";
    // Deferred one tick, like a lesson's drag (Task 71/84): changing the
    // dragged element's look inside dragstart can cancel the drag.
    window.setTimeout(() => {
      setAdjustedTimeSlotId(null);
      adjustment.clearSelection();
      setSelectedCardKey(null);
      setDraggingCardKey(card.key);
    }, 0);
  }

  function handleCardDragEnd(): void {
    setDraggingCardKey(null);
  }

  function handleChooseTeacher(card: PlacementCard, teacherId: number | null): void {
    setChosenTeacherByCard((previous) => {
      const next = new Map(previous);
      if (teacherId === null) {
        next.delete(card.key);
      } else {
        next.set(card.key, teacherId);
      }
      return next;
    });
    if (teacherId === null && selectedCardKey === card.key) {
      setSelectedCardKey(null);
    }
  }

  function handleChooseRoom(card: PlacementCard, roomId: number | null): void {
    setChosenRoomByCard((previous) => new Map(previous).set(card.key, roomId));
  }

  // Drop or 「放到這裡」. A cell the backend refuses (gray) sends nothing.
  function handlePlaceOnCell(timeSlot: TimeSlot): void {
    const card = placingCard;
    if (card === null) {
      return;
    }
    const teacherId = teacherForCard(card, chosenTeacherByCard);
    if (teacherId === null) {
      placeHintFlash.showFlash(PLACE_REFUSAL_MESSAGES.TEACHER_REQUIRED);
      return;
    }
    const mark = placeCandidateData?.lesson_id === card.anchorLessonId ? placeMarks?.cells.get(timeSlot.id) : undefined;
    if (mark?.status === "blocked") {
      placeHintFlash.showFlash(`無法放在這裡：${mark.reason}`);
      return;
    }
    setAdjustedTimeSlotId(null);
    setDraggingCardKey(null);
    placement.requestPreview({
      card,
      timeSlotId: timeSlot.id,
      teacherId,
      roomId: roomForCard(card, chosenRoomByCard),
    });
  }

  function handlePlacementSaved({ request, result }: SavedPlacement): void {
    focusAfterReloadRef.current = null;
    refreshAfterAdjustment();
    setAdjustedTimeSlotId(firstPlacedSlot(result.changes, request.card.lessonIds));
    adjustmentFlash.showFlash("已放入並儲存");
    setSelectedCardKey(null);
  }

  function handleConfirmPlacement(): void {
    void placement.confirm().then((saved) => {
      if (saved !== null) {
        handlePlacementSaved(saved);
      }
    });
  }

  // After closing the preview: back to the card, else the timetable.
  function restoreFocusAfterPlacement(): void {
    const key = placement.preview?.request.card.key ?? null;
    const cardButton =
      key === null ? null : document.querySelector<HTMLElement>(`[data-place-card="${key}"]`);
    cardButton?.focus();
    if (cardButton === null || document.activeElement !== cardButton) {
      timetableSectionRef.current?.focus();
    }
  }

  // --- Task 95: changing the room of the selected lesson ---

  function handleRoomChangePreview(roomId: number | null, scope: RoomChangeScope): void {
    if (selectedLesson === null) {
      return;
    }
    previewedLessonIdRef.current = selectedLesson.scheduleId;
    roomChange.requestPreview({ lesson: selectedLesson, roomId, scope });
  }

  function handleRoomChangeSaved({ request }: SavedRoomChange): void {
    focusAfterReloadRef.current = request.lesson.scheduleId;
    refreshAfterAdjustment();
    adjustmentFlash.showFlash("已更改教室並儲存");
    adjustment.clearSelection();
  }

  function handleConfirmRoomChange(): void {
    void roomChange.confirm().then((saved) => {
      if (saved !== null) {
        handleRoomChangeSaved(saved);
      }
    });
  }

  function handleConfirmAdjustment(): void {
    void adjustment.confirm().then((saved) => {
      if (saved !== null) {
        handleAdjustmentSaved(saved);
      }
    });
  }

  function roomNameOf(roomId: number | null): string | null {
    return (roomsResource.data ?? []).find((room) => room.id === roomId)?.name ?? null;
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
  // The record's 導師 (its 教師設定): a tag under a class's grid, and their
  // name as a tag on the lessons they teach that class.
  const homeroomByClass = new Map(
    (recordTeachers.data ?? [])
      .filter((teacher) => teacher.homeroom_class_id !== null)
      .map((teacher) => [teacher.homeroom_class_id as number, teacher]),
  );
  const homeroomTeacherByClass = new Map(
    [...homeroomByClass].map(([classId, teacher]) => [classId, teacher.teacher_id]),
  );
  const homeroomOfSelectedClass =
    viewMode === "class" && selectedTargetId !== null ? homeroomByClass.get(selectedTargetId) : undefined;
  // The class has a 合併節 listing several teachers (its own marked *).
  const showsCombinedTeacherNote =
    viewMode === "class" &&
    selectedTargetId !== null &&
    displaySchedules.some(
      (row) => row.classId === selectedTargetId && row.teacherName !== null && row.teacherName.includes("*"),
    );
  // Editing is only ever in effect for a 教學組長 in a working copy.
  const isEditing = isEditModeOn;
  // 換教師 is only for a copied timetable (複製自編號 x).
  const canReassign = isEditing && selectedVersion?.status === "COPIED";
  // 複製此課表's targets: the semesters of the record's own academic year.
  const recordSemester =
    selectedVersion === undefined ? undefined : semesterById.get(selectedVersion.semester_id);
  const copyTargetSemesters = (semesters.data ?? [])
    .filter((semester) => semester.academic_year_id === recordSemester?.academic_year_id)
    .sort((a, b) => a.number - b.number);
  const otherPublished =
    selectedVersion === undefined
      ? undefined
      : versions.find(
          (version) =>
            version.semester_id === selectedVersion.semester_id &&
            version.is_published &&
            version.id !== selectedVersion.id,
        );

  // Task 99: 「王老師(teacher11)」 when two teachers share a name.
  const teacherAccountById = timetable.data?.lookups.teacherAccountById ?? new Map<number, string>();
  const teacherLabelOf = (teacherId: number, name: string): string =>
    formatTeacherName(name, teacherAccountById.get(teacherId));
  const teacherAccounts = new Set(teacherAccountById.values());

  // Task 102: 停用 classes / teachers / rooms only when this record's
  // timetable uses them, marked 「（已停用）」 (utils/choiceSelect.ts).
  const usedClassIds = new Set(schedules.map((row) => row.classId));
  const usedTeacherIds = new Set(
    schedules.map((row) => row.teacherId).filter((id): id is number => id !== null),
  );
  const usedRoomIds = new Set(schedules.map((row) => row.roomId).filter((id): id is number => id !== null));
  const classChoices = (classesResource.data ?? []).map((item) => ({
    id: item.id,
    label: item.name,
    isActive: item.is_active,
  }));
  const targetOptions =
    viewMode === "class"
      ? viewableChoices(classChoices, usedClassIds)
      : viewMode === "teacher"
        ? viewableChoices(
            (teachersResource.data ?? []).map((item) => ({
              id: item.id,
              label: teacherLabelOf(item.id, item.name),
              isActive: item.is_active,
            })),
            usedTeacherIds,
          )
        : [
            // Every class's own classroom first (原班上課, no Room record;
            // shown by the class's name alone), then the school's rooms.
            ...viewableChoices(classChoices, usedClassIds).map((item) => ({
              id: homeroomTargetId(item.id),
              label: item.label,
            })),
            ...viewableChoices(
              (roomsResource.data ?? []).map((item) => ({ id: item.id, label: item.name, isActive: item.is_active })),
              usedRoomIds,
            ),
          ];

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
  const checkTagInput = {
    isChecking: scheduleCheck.isChecking,
    hasFailed: scheduleCheck.errorMessage !== null,
    hasResult: scheduleCheck.result !== null && checkLookups !== null,
    errorCount: checkProblemCount,
    warningCount: checkWarningCount,
  };
  const checkTagState = checkTags(checkTagInput);
  const isCheckOpen = isCheckListOpen(
    checkTagInput,
    checkListToggle !== null && checkListToggle.result === scheduleCheck.result ? checkListToggle.open : null,
  );

  const selectedLessonSlotLabel =
    selectedLesson === null || checkLookups === null
      ? ""
      : resolveTimeSlotLabel(selectedLesson.timeSlotId, checkLookups);

  return (
    <div className={PAGE}>
      {confirmDialog}
      {isAdmin && !isEditing && (
        <p className="mb-3">
          <Link to="/records" className={BUTTON_GHOST}>
            ← 返回排課紀錄
          </Link>
        </p>
      )}
      <PageHeader
        title={isAdmin && selectedVersion !== undefined ? `課表・編號 ${selectedVersion.display_number}` : "課表"}
        info={
          isAdmin && selectedVersion !== undefined && !isEditing ? (
            <p>
              {selectedVersion.status === "MANUAL" && !selectedVersion.is_published
                ? "手動編輯後按「儲存課表」會直接更新這筆手動排課紀錄。"
                : "手動編輯後按「儲存課表」會另存成一筆新的「手動排課」紀錄，這份課表不會改變。"}
              {selectedVersion.status === "COPIED" && "複製的課表在手動編輯時可以換教師。"}
            </p>
          ) : undefined
        }
        meta={
          isAdmin &&
          selectedVersion !== undefined && (
            <>
              <span className={META_TAG}>{semesterLabelOf(selectedVersion, semesterById, academicYearById)}</span>
              <RecordStatusBadge record={selectedVersion} />
              {isEditing && <StatusBadge tone="warning">編輯中・未儲存</StatusBadge>}
            </>
          )
        }
        actions={
          !isAdmin || selectedVersion === undefined ? undefined : isEditing ? (
            // 儲存課表 sits top right while editing.
            <>
              {canReassign && (
                <button
                  type="button"
                  onClick={() => setIsReassignPanelOpen((previous) => !previous)}
                  aria-expanded={isReassignPanelOpen}
                  className={BUTTON_SECONDARY}
                >
                  {isReassignPanelOpen ? "收合換教師" : "換教師"}
                </button>
              )}
              <button
                type="button"
                onClick={() => void handleCancelEditing()}
                disabled={isRecordBusy || isBusy}
                className={BUTTON_SECONDARY}
              >
                取消編輯
              </button>
              <button
                type="button"
                onClick={() => void handleSaveEditing()}
                disabled={isRecordBusy || isBusy}
                className={BUTTON_PRIMARY}
              >
                {isRecordBusy ? "儲存中…" : "儲存課表"}
              </button>
            </>
          ) : (
            // v3: the record's actions -- secondary ones first, 發布 (the
            // last step) on the right; a published one shows its badge.
            <>
              <button
                type="button"
                onClick={() => void handleStartEditing()}
                disabled={isRecordBusy || !hasTimetable(selectedVersion.status)}
                className={BUTTON_SECONDARY}
              >
                {isRecordBusy ? "處理中…" : "手動編輯課表"}
              </button>
              <button
                type="button"
                onClick={() => openRecordAction("copy")}
                disabled={isRecordBusy}
                className={BUTTON_SECONDARY}
              >
                複製此課表
              </button>
              {selectedVersion.is_published ? (
                <StatusBadge tone="success">✓ 已發布</StatusBadge>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleStartPublish()}
                  disabled={isRecordBusy}
                  className={BUTTON_SUCCESS}
                >
                  發布此課表
                </button>
              )}
            </>
          )
        }
      />
      {/* Task 100: the check result, right under the title row -- the same
          tags in the view and the edit mode (教學組長 only). */}
      {canCheck && selectedVersion !== undefined && (
        <>
          <CheckStatusTag
            state={checkTagState}
            isOpen={isCheckOpen}
            onToggle={() => setCheckListToggle({ result: scheduleCheck.result, open: !isCheckOpen })}
            errorMessage={scheduleCheck.errorMessage}
            onRetry={scheduleCheck.run}
            listId="timetable-check-list"
          />
          {isCheckOpen && scheduleCheck.result !== null && checkLookups !== null && (
            <div id="timetable-check-list" className={`${CARD} mb-4`}>
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
        </>
      )}
      {recordFlash.message !== null && <p className={`${SUCCESS_TEXT} mb-3`}>✓ {recordFlash.message}</p>}
      {recordError !== null && recordAction === null && (
        <p role="alert" className={`${ERROR_TEXT} mb-3`}>
          {recordError}
        </p>
      )}
      {isRequestedVersionMissing && (
        <p className={`${NOTICE} mb-4`}>指定的排課紀錄已不存在（可能已被刪除）。</p>
      )}

      {/* A 一般老師 picks among the published records (the backend lists
          nothing else for them); the 教學組長 opens one from 排課紀錄. */}
      {!isAdmin && (
        <section className={SECTION}>
          <label htmlFor="timetable-version-select" className={`${LABEL} mb-1 block`}>
            選擇學期的課表
          </label>
          {versions.length === 0 ? (
            <p className={MUTED_TEXT}>目前沒有已發布的課表，教學組長發布課表後就會出現在這裡。</p>
          ) : (
            <select
              id="timetable-version-select"
              value={selectedVersionId ?? ""}
              onChange={(event) =>
                handleSelectVersion(event.target.value === "" ? null : Number(event.target.value))
              }
              className={`${SELECT} ${FIELD_PAGE}`}
            >
              <option value="">請選擇…</option>
              {versions.map((version) => (
                <option key={version.id} value={version.id}>
                  {semesterLabelOf(version, semesterById, academicYearById)}
                </option>
              ))}
            </select>
          )}
        </section>
      )}
      {isAdmin && selectedVersionId === null && !isRequestedVersionMissing && (
        <p className={MUTED_TEXT}>
          請從
          <Link to="/records" className={LINK_TEXT}>
            排課紀錄
          </Link>
          選擇要檢視的課表。
        </p>
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
          {/* Task 99: one control row -- the view tabs, the class / teacher /
              room picker (and the class's 導師), then at the right the (i)
              and, while editing, the conflict check's tag. */}
          <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <nav className="flex gap-2" aria-label="檢視方式">
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
              <select
                id="timetable-target-select"
                aria-label={viewMode === "class" ? "選擇班級" : viewMode === "teacher" ? "選擇教師" : "選擇教室"}
                value={selectedTargetId ?? ""}
                onChange={(event) => {
                  setSelectedTargetId(
                    event.target.value === "" ? null : Number(event.target.value),
                  );
                  setLocateMark(null);
                }}
                className={`${SELECT} ${FIELD_PAGE}`}
              >
                <option value="">
                  {viewMode === "class" ? "選擇班級…" : viewMode === "teacher" ? "選擇教師…" : "選擇教室…"}
                </option>
                {targetOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
              {homeroomOfSelectedClass !== undefined && (
                <span className={HOMEROOM_TAG}>
                  導師：{teacherLabelOf(homeroomOfSelectedClass.teacher_id, homeroomOfSelectedClass.teacher_name)}
                </span>
              )}
            </div>
            {isEditing && (
              <div className="flex items-center gap-2">
                <InfoPopover label="關於手動編輯">
                  <p>
                    點選課程後可移動或對調，也可直接拖曳；改完按「儲存課表」。點一堂課選取它，再點「移到這裡」移動，或點另一堂課與它對調；也可以直接把課拖到空格（移動）或另一堂課上（對調）。每次異動都會先預覽。改完按右上角「儲存課表」。
                  </p>
                  <p className="mt-2">每次調整後都會自動依目前的課表檢查所有排課規則；標題下方的標籤是檢查結果，有錯誤或警告時清單會自動展開，點標籤可以展開或收起。</p>
                </InfoPopover>
              </div>
            )}
          </div>
          {showsCombinedTeacherNote && (
            <p className="mb-4 text-sm text-gray-600">
              課表中多位老師共同上課時，名稱註記*者，為該節課本班授課老師。
            </p>
          )}
          {/* Task 103: the short-lived notices float at the bottom of the
              window (styles/ui.ts TOAST_REGION): seen wherever the page is
              scrolled, and never moving the timetable when they come and
              go -- a notice that vanished right as a lesson was pressed used
              to shift the grid out from under the pointer. */}
          {isEditing && (
            <div className={TOAST_REGION}>
              {adjustmentFlash.message !== null && (
                <p role="status" className={TOAST_SUCCESS}>
                  ✓ {adjustmentFlash.message}
                </p>
              )}
              {blockedFlash.message !== null && (
                <p role="alert" className={TOAST_NOTICE}>
                  無法放在這裡：{blockedFlash.message}
                </p>
              )}
              {placeHintFlash.message !== null && (
                <p role="alert" className={TOAST_NOTICE}>
                  {placeHintFlash.message}
                </p>
              )}
              {placement.phase === "loadingPreview" && (
                <p className={TOAST_LOADING} aria-live="polite">
                  正在預覽放入結果…
                </p>
              )}
              {roomChange.phase === "loadingPreview" && (
                <p className={TOAST_LOADING} aria-live="polite">
                  正在預覽更改教室的結果…
                </p>
              )}
              {adjustment.phase === "loadingPreview" && (
                <p className={TOAST_LOADING} aria-live="polite">
                  正在預覽異動結果…
                </p>
              )}
            </div>
          )}
          {/* Task 69: editing (v3: in the working copy). */}
          {isEditing && (
            <div className="mb-4 flex flex-col gap-2 empty:hidden">
              {placement.previewError !== null && (
                <p role="alert" className={ERROR_TEXT}>
                  無法預覽這次放入，已取消：{placement.previewError}
                </p>
              )}
              {isEditing && selectedCard !== null && placement.phase === "idle" && (
                <div className={SELECTION_BAR} aria-live="polite">
                  <span>
                    已選取：{selectedCard.className} {selectedCard.label}。點「放到這裡」放入
                  </span>
                  <label className="inline-flex items-center gap-1">
                    <span>教室</span>
                    <select
                      aria-label="放入的教室"
                      value={roomForCard(selectedCard, chosenRoomByCard) ?? ""}
                      onChange={(event) =>
                        handleChooseRoom(
                          selectedCard,
                          event.target.value === "" ? null : Number(event.target.value),
                        )
                      }
                      className="rounded border border-blue-300 bg-white px-1 py-0.5 text-sm"
                    >
                      {(roomForCard(selectedCard, chosenRoomByCard) === null ||
                        canChooseNoRoom(selectedCard)) && <option value="">不指定教室</option>}
                      {(roomsResource.data ?? []).map((room) => (
                        <option key={room.id} value={room.id}>
                          {room.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    onClick={() => setSelectedCardKey(null)}
                    className={BUTTON_SECONDARY_SM}
                  >
                    取消
                  </button>
                  {/* Task 98: the requirement's special room. */}
                  {requiredRoomHint(selectedCard, roomNameOf) !== null && (
                    <span className="w-full text-gray-700" role="status">
                      {requiredRoomHint(selectedCard, roomNameOf)}
                    </span>
                  )}
                </div>
              )}
              {roomChange.previewError !== null && (
                <p role="alert" className={ERROR_TEXT}>
                  無法預覽這次更改，已取消：{roomChange.previewError}
                </p>
              )}
              {adjustment.previewError !== null && (
                <p role="alert" className={ERROR_TEXT}>
                  無法預覽這次異動，已取消：{adjustment.previewError}
                </p>
              )}
              {isEditing && selectedLesson !== null && adjustment.phase === "idle" && (
                <div className={SELECTION_BAR} aria-live="polite">
                  <span>
                    已選取：{selectedLesson.className} {selectedLesson.subjectName}（
                    {selectedLessonSlotLabel}）。點選「移到這裡」移動，或點選另一堂課與它對調
                  </span>
                  {canChangeRoom({
                    isAdmin,
                    versionStatus: isEditing ? "EDITING" : null,
                    isEditModeOn,
                    hasSelectedLesson: true,
                  }) && (
                    <RoomChangeControls
                      key={selectedLesson.scheduleId}
                      lesson={selectedLesson}
                      rooms={roomsResource.data}
                      requiredRoomId={
                        timetable.data?.lookups.requirementById.get(selectedLesson.requirementId)
                          ?.required_room_id ?? null
                      }
                      disabled={isBusy || timetable.isLoading}
                      onPreview={handleRoomChangePreview}
                    />
                  )}
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

          {canReassign && isReassignPanelOpen && timetable.data !== null && editingId !== null && (
            <TeacherReassignPanel
              key={editingId}
              scheduleVersionId={editingId}
              timetable={timetable.data}
              disabled={timetable.isLoading}
              onSaved={handleReassignmentSaved}
            />
          )}

          {isEditing && lessonCount(placementCards) > 0 && (
            <UnscheduledLessonsPanel
              cards={cardsForView(placementCards, viewMode, selectedTargetId, showAllClasses)}
              totalLessonCount={lessonCount(placementCards)}
              showAllToggle={
                viewMode === "class" && selectedTargetId !== null
                  ? { showAll: showAllClasses, onToggle: () => setShowAllClasses((value) => !value) }
                  : null
              }
              chosenTeacherByCard={chosenTeacherByCard}
              teacherLabel={teacherLabelOf}
              onChooseTeacher={handleChooseTeacher}
              selectedCardKey={selectedCardKey}
              draggingCardKey={draggingCardKey}
              disabled={isBusy || timetable.isLoading}
              errorMessage={unscheduled.errorMessage}
              onCardClick={handleCardClick}
              onCardDragStart={handleCardDragStart}
              onCardDragEnd={handleCardDragEnd}
            />
          )}
          {isEditing && unscheduled.errorMessage !== null && lessonCount(placementCards) === 0 && (
            <p role="alert" className={ERROR_TEXT}>
              無法載入未排入課程：{unscheduled.errorMessage}
            </p>
          )}

          {timetable.isLoading && <p className={LOADING_TEXT}>載入中…</p>}
          {timetable.errorMessage !== null && (
            <p role="alert" className={ERROR_TEXT}>
              {timetable.errorMessage}
            </p>
          )}

          {/* Task 84: only while marks are shown. */}
          {isEditing && shownMarks !== null && (
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
              homeroomTeacherByClass={homeroomTeacherByClass}
              teacherAccounts={teacherAccounts}
              periods={periods}
              periodDisplay={periodDisplay}
              schedules={displaySchedules}
              viewMode={viewMode}
              targetId={selectedTargetId}
              timeSlotByWeekdayAndPeriod={timeSlotByWeekdayAndPeriod}
              highlightedTimeSlotId={visibleLocateSlot(
                locateMark,
                { versionId: activeVersionId, isEditing, viewMode, targetId: selectedTargetId },
                scheduleCheck.result?.violations ?? null,
              )}
              adjustedTimeSlotId={isEditing ? adjustedTimeSlotId : null}
              edit={
                isEditing
                  ? {
                      selected: selectedLesson,
                      disabled: isBusy || timetable.isLoading,
                      lessonById: timetable.data.lookups.lessonById ?? new Map(),
                      onLessonClick: handleLessonClick,
                      onMoveHere: handleMoveHere,
                      // Starting a drag drops any click selection first.
                      onDragStartLesson: handleDragStartLesson,
                      onDragEndLesson: handleDragEndLesson,
                      onDropOnCell: handleDropOnCell,
                      onDropOnLesson: handleDropOnLesson,
                      candidateMarks: shownMarks,
                      placing: placingCard === null ? null : { isDragging: draggingCard !== null },
                      onPlaceOnCell: handlePlaceOnCell,
                    }
                  : null
              }
            />
          )}
          {isEditing && shownCandidateSourceId !== null && candidateState.status === "failed" && (
            <p className={`${MUTED_TEXT} mt-2`}>目前無法顯示候選位置，仍可直接放下並預覽</p>
          )}
          {isEditing && placingCard !== null && placeCandidateState.status === "failed" && (
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
      {timetable.data !== null && (
        <RoomChangePreviewDialog
          preview={roomChange.preview}
          lookups={timetable.data.lookups}
          isSaving={roomChange.phase === "saving"}
          saveError={roomChange.saveError}
          onConfirm={handleConfirmRoomChange}
          onCancel={roomChange.closePreview}
          restoreFocusFallback={restoreFocusAfterPreview}
        />
      )}
      {/* Task 99: lessons still missing -- a warning instead of the
          publish confirmation. */}
      <ConfirmDialog
        open={publishBlocked !== null}
        title={PUBLISH_BLOCKED_TITLE}
        cancelLabel="關閉"
        showConfirm={false}
        onConfirm={() => setPublishBlocked(null)}
        onCancel={() => setPublishBlocked(null)}
      >
        <p>{publishBlocked}</p>
      </ConfirmDialog>
      {/* v3: 發布此課表 */}
      {selectedVersion !== undefined && (
        <ConfirmDialog
          open={recordAction === "publish"}
          title="發布這份課表？"
          confirmLabel="發布課表"
          tone="success"
          busy={isRecordBusy}
          busyLabel="發布中…"
          onConfirm={() => void handleConfirmPublish()}
          onCancel={() => setRecordAction(null)}
        >
          <p>即將發布「{formatVersionLabel(selectedVersion, semesterById, academicYearById)}」，老師就能在課表看到它。</p>
          {otherPublished !== undefined && (
            <p className="mt-2">
              同學期原本發布的「{formatVersionLabel(otherPublished, semesterById, academicYearById)}
              」會改為未發布（紀錄本身保留）。
            </p>
          )}
          {recordError !== null && (
            <p role="alert" className={ERROR_TEXT}>
              {recordError}
            </p>
          )}
        </ConfirmDialog>
      )}
      {/* v3: 複製此課表 -- any semester of the same academic year. */}
      {selectedVersion !== undefined && (
        <ConfirmDialog
          open={recordAction === "copy"}
          title="複製這份課表？"
          confirmLabel="複製課表"
          busy={isRecordBusy}
          busyLabel="複製中…"
          confirmDisabled={copyTargetSemesterId === null}
          onConfirm={() => void handleConfirmCopy()}
          onCancel={() => setRecordAction(null)}
        >
          <p>
            會複製這份課表與它的排課設定，產生一筆新的排課紀錄（複製自編號 {selectedVersion.display_number}
            ）。可以選擇同一學年度的另一個學期，例如下學期老師有異動時，複製後在手動編輯中換教師。
          </p>
          <label className="mt-3 flex flex-col gap-1">
            <span className={LABEL}>複製到學期</span>
            <select
              value={copyTargetSemesterId ?? ""}
              onChange={(event) =>
                setCopyTargetSemesterId(event.target.value === "" ? null : Number(event.target.value))
              }
              className={`${SELECT} w-full`}
            >
              {copyTargetSemesters.map((semester) => (
                <option key={semester.id} value={semester.id}>
                  {formatSemesterLabel(semester, academicYearById)}
                  {semester.id === selectedVersion.semester_id ? "（原學期）" : ""}
                </option>
              ))}
            </select>
          </label>
          {copyTargetSemesters.length < 2 && (
            <p className={`${MUTED_TEXT} mt-2`}>
              這個學年度目前只有一個學期；要複製到另一個學期，請先在「開始排課」建立該學期。
            </p>
          )}
          {recordError !== null && (
            <p role="alert" className={ERROR_TEXT}>
              {recordError}
            </p>
          )}
        </ConfirmDialog>
      )}
      {timetable.data !== null && (
        <PlacementPreviewDialog
          preview={placement.preview}
          lookups={timetable.data.lookups}
          isSaving={placement.phase === "saving"}
          saveError={placement.saveError}
          onConfirm={handleConfirmPlacement}
          onCancel={placement.closePreview}
          restoreFocusFallback={restoreFocusAfterPlacement}
        />
      )}
    </div>
  );
}
