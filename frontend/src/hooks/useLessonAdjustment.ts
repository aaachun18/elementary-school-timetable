import { useEffect, useRef, useState } from "react";
import {
  check as checkScheduleVersion,
  moveLesson,
  swapLessons,
} from "../api/scheduleVersions";
import { extractApiErrorMessage } from "../constants/errorMessages";
import type { EnrichedSchedule } from "./useTimetableData";
import type { ScheduleAdjustmentResult, ScheduleCheckResult } from "../types/scheduler";

// One change the user picked on the grid, not yet saved.
export type LessonAdjustment =
  | { kind: "move"; lesson: EnrichedSchedule; targetTimeSlotId: number }
  | { kind: "swap"; lesson: EnrichedSchedule; other: EnrichedSchedule };

export interface AdjustmentPreview {
  adjustment: LessonAdjustment;
  // GET check right before the preview: the version as it is now.
  before: ScheduleCheckResult;
  // The same change with dry_run: what saving it would do.
  after: ScheduleAdjustmentResult;
}

// idle: nothing in flight (a lesson may be selected).
// loadingPreview: the two preview requests are in flight.
// previewing: the preview dialog is open, waiting for 確認 / 返回.
// saving: the real (dry_run=false) request is in flight.
export type AdjustmentPhase = "idle" | "loadingPreview" | "previewing" | "saving";

export interface SavedAdjustment {
  adjustment: LessonAdjustment;
  result: ScheduleAdjustmentResult;
}

interface UseLessonAdjustmentResult {
  phase: AdjustmentPhase;
  selectedScheduleId: number | null;
  preview: AdjustmentPreview | null;
  // The preview requests failed; the action was dropped (shown on the page).
  previewError: string | null;
  // Saving failed; shown inside the still-open preview dialog.
  saveError: string | null;
  toggleSelection: (scheduleId: number) => void;
  clearSelection: () => void;
  requestPreview: (adjustment: LessonAdjustment) => void;
  closePreview: () => void;
  // Resolves with what was saved, or null if it failed / was superseded.
  confirm: () => Promise<SavedAdjustment | null>;
  reset: () => void;
}

function callAdjustment(
  versionId: number,
  adjustment: LessonAdjustment,
  dryRun: boolean,
): Promise<ScheduleAdjustmentResult> {
  if (adjustment.kind === "move") {
    return moveLesson(versionId, {
      schedule_id: adjustment.lesson.scheduleId,
      target_time_slot_id: adjustment.targetTimeSlotId,
      dry_run: dryRun,
    });
  }
  return swapLessons(versionId, {
    schedule_id: adjustment.lesson.scheduleId,
    swap_with_schedule_id: adjustment.other.scheduleId,
    dry_run: dryRun,
  });
}

// Task 69: the click-to-move/swap flow of the timetable's edit mode:
// select a lesson -> pick a target -> preview (before/after checks) ->
// confirm -> save. Only one request is ever in flight; any response that
// arrives after reset() (e.g. on a version change) or unmount is dropped.
export function useLessonAdjustment(scheduleVersionId: number | null): UseLessonAdjustmentResult {
  const [phase, setPhase] = useState<AdjustmentPhase>("idle");
  const [selectedScheduleId, setSelectedScheduleId] = useState<number | null>(null);
  const [preview, setPreview] = useState<AdjustmentPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const latestRequestRef = useRef(0);
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const startRequest = (): (() => boolean) => {
    latestRequestRef.current += 1;
    const requestNumber = latestRequestRef.current;
    return () => isMountedRef.current && requestNumber === latestRequestRef.current;
  };

  // Back to nothing selected and nothing in flight (e.g. leaving edit mode
  // or switching versions); a late response is then dropped.
  const reset = (): void => {
    latestRequestRef.current += 1;
    setPhase("idle");
    setSelectedScheduleId(null);
    setPreview(null);
    setPreviewError(null);
    setSaveError(null);
  };

  // Clicking the selected lesson again deselects it. Ignored while a
  // request is in flight or the preview is open.
  const toggleSelection = (scheduleId: number): void => {
    if (phase !== "idle") {
      return;
    }
    setPreviewError(null);
    setSelectedScheduleId((previous) => (previous === scheduleId ? null : scheduleId));
  };

  const clearSelection = (): void => {
    if (phase !== "idle") {
      return;
    }
    setSelectedScheduleId(null);
  };

  const requestPreview = (adjustment: LessonAdjustment): void => {
    if (scheduleVersionId === null || phase !== "idle") {
      return;
    }
    const versionId = scheduleVersionId;
    const isCurrent = startRequest();
    setPhase("loadingPreview");
    setPreviewError(null);
    setSaveError(null);
    Promise.all([
      checkScheduleVersion(versionId),
      callAdjustment(versionId, adjustment, true),
    ])
      .then(([before, after]) => {
        if (isCurrent()) {
          setPreview({ adjustment, before, after });
          setPhase("previewing");
        }
      })
      .catch((caught: unknown) => {
        // Nothing half-done is left behind: no dialog, no selection.
        if (isCurrent()) {
          setPreviewError(extractApiErrorMessage(caught));
          setSelectedScheduleId(null);
          setPhase("idle");
        }
      });
  };

  // 返回: back to idle with the lesson still selected, so another target
  // can be picked straight away.
  const closePreview = (): void => {
    if (phase !== "previewing") {
      return;
    }
    setPreview(null);
    setSaveError(null);
    setPhase("idle");
  };

  const confirm = async (): Promise<SavedAdjustment | null> => {
    if (scheduleVersionId === null || phase !== "previewing" || preview === null) {
      return null;
    }
    const versionId = scheduleVersionId;
    const { adjustment } = preview;
    const isCurrent = startRequest();
    setPhase("saving");
    setSaveError(null);
    try {
      const result = await callAdjustment(versionId, adjustment, false);
      if (!isCurrent()) {
        return null;
      }
      setPreview(null);
      setSelectedScheduleId(null);
      setPhase("idle");
      return { adjustment, result };
    } catch (caught) {
      if (isCurrent()) {
        setSaveError(extractApiErrorMessage(caught));
        setPhase("previewing");
      }
      return null;
    }
  };

  return {
    phase,
    selectedScheduleId,
    preview,
    previewError,
    saveError,
    toggleSelection,
    clearSelection,
    requestPreview,
    closePreview,
    confirm,
    reset,
  };
}
