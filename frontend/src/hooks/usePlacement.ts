import { useEffect, useRef, useState } from "react";
import { check as checkScheduleVersion, placeLesson } from "../api/scheduleVersions";
import { extractApiErrorMessage } from "../constants/errorMessages";
import {
  PLACE_REFUSAL_MESSAGES,
  placeRefusalReasonOf,
  type PlacementCard,
} from "../utils/placement";
import type { PlaceLessonResult, ScheduleCheckResult } from "../types/scheduler";

// One placement the user picked, not yet saved.
export interface PlacementRequest {
  card: PlacementCard;
  timeSlotId: number;
  teacherId: number;
  // null: the backend's default room (see utils/placement.ts).
  roomId: number | null;
}

export interface PlacementPreview {
  request: PlacementRequest;
  // GET check right before the preview: the version as it is now.
  before: ScheduleCheckResult;
  // The same placement with dry_run: what saving it would do.
  after: PlaceLessonResult;
}

export type PlacementPhase = "idle" | "loadingPreview" | "previewing" | "saving";

export interface SavedPlacement {
  request: PlacementRequest;
  result: PlaceLessonResult;
}

interface UsePlacementResult {
  phase: PlacementPhase;
  preview: PlacementPreview | null;
  // The preview requests failed; the placement was dropped (on the page).
  previewError: string | null;
  // Saving failed; shown inside the still-open preview dialog.
  saveError: string | null;
  requestPreview: (request: PlacementRequest) => void;
  closePreview: () => void;
  confirm: () => Promise<SavedPlacement | null>;
  reset: () => void;
}

function callPlace(versionId: number, request: PlacementRequest, dryRun: boolean): Promise<PlaceLessonResult> {
  return placeLesson(versionId, {
    lesson_id: request.card.anchorLessonId,
    time_slot_id: request.timeSlotId,
    teacher_id: request.teacherId,
    room_id: request.roomId,
    dry_run: dryRun,
  });
}

// A 409 with a known reason reads as the grid's own hint; anything else
// shows the backend's Chinese detail (never a code).
function messageOf(caught: unknown): string {
  const reason = placeRefusalReasonOf(caught);
  return reason !== null ? PLACE_REFUSAL_MESSAGES[reason] : extractApiErrorMessage(caught);
}

// Task 93: drop or click an unscheduled card on a cell -> preview (the
// check before vs. place-lesson with dry_run) -> confirm -> save. The same
// flow as useLessonAdjustment (Task 69): one request in flight; anything
// arriving after reset() or unmount is dropped.
export function usePlacement(scheduleVersionId: number | null): UsePlacementResult {
  const [phase, setPhase] = useState<PlacementPhase>("idle");
  const [preview, setPreview] = useState<PlacementPreview | null>(null);
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

  const reset = (): void => {
    latestRequestRef.current += 1;
    setPhase("idle");
    setPreview(null);
    setPreviewError(null);
    setSaveError(null);
  };

  const requestPreview = (request: PlacementRequest): void => {
    if (scheduleVersionId === null || phase !== "idle") {
      return;
    }
    const versionId = scheduleVersionId;
    const isCurrent = startRequest();
    setPhase("loadingPreview");
    setPreviewError(null);
    setSaveError(null);
    Promise.all([checkScheduleVersion(versionId), callPlace(versionId, request, true)])
      .then(([before, after]) => {
        if (isCurrent()) {
          setPreview({ request, before, after });
          setPhase("previewing");
        }
      })
      .catch((caught: unknown) => {
        if (isCurrent()) {
          setPreviewError(messageOf(caught));
          setPhase("idle");
        }
      });
  };

  const closePreview = (): void => {
    if (phase !== "previewing") {
      return;
    }
    setPreview(null);
    setSaveError(null);
    setPhase("idle");
  };

  const confirm = async (): Promise<SavedPlacement | null> => {
    if (scheduleVersionId === null || phase !== "previewing" || preview === null) {
      return null;
    }
    const versionId = scheduleVersionId;
    const { request } = preview;
    const isCurrent = startRequest();
    setPhase("saving");
    setSaveError(null);
    try {
      const result = await callPlace(versionId, request, false);
      if (!isCurrent()) {
        return null;
      }
      setPreview(null);
      setPhase("idle");
      return { request, result };
    } catch (caught) {
      if (isCurrent()) {
        setSaveError(messageOf(caught));
        setPhase("previewing");
      }
      return null;
    }
  };

  return { phase, preview, previewError, saveError, requestPreview, closePreview, confirm, reset };
}
