import { useEffect, useRef, useState } from "react";
import { changeRoom, check as checkScheduleVersion } from "../api/scheduleVersions";
import { extractApiErrorMessage } from "../constants/errorMessages";
import type { EnrichedSchedule } from "./useTimetableData";
import type { ChangeRoomResult, RoomChangeScope, ScheduleCheckResult } from "../types/scheduler";

// One room change the user picked, not yet saved. roomId null clears it.
export interface RoomChangeRequest {
  lesson: EnrichedSchedule;
  roomId: number | null;
  scope: RoomChangeScope;
}

export interface RoomChangePreview {
  request: RoomChangeRequest;
  // GET check right before the preview: the version as it is now.
  before: ScheduleCheckResult;
  // The same change with dry_run: what saving it would do.
  after: ChangeRoomResult;
}

export type RoomChangePhase = "idle" | "loadingPreview" | "previewing" | "saving";

export interface SavedRoomChange {
  request: RoomChangeRequest;
  result: ChangeRoomResult;
}

interface UseRoomChangeResult {
  phase: RoomChangePhase;
  preview: RoomChangePreview | null;
  previewError: string | null;
  saveError: string | null;
  requestPreview: (request: RoomChangeRequest) => void;
  closePreview: () => void;
  confirm: () => Promise<SavedRoomChange | null>;
  reset: () => void;
}

function callChangeRoom(versionId: number, request: RoomChangeRequest, dryRun: boolean): Promise<ChangeRoomResult> {
  return changeRoom(versionId, {
    schedule_id: request.lesson.scheduleId,
    room_id: request.roomId,
    scope: request.scope,
    dry_run: dryRun,
  });
}

// Task 95: 「更改教室」 -- preview (the check before vs. change-room with
// dry_run) -> confirm -> save, the same flow as useLessonAdjustment and
// usePlacement: one request in flight; anything arriving after reset() or
// unmount is dropped. Errors are the backend's Chinese detail.
export function useRoomChange(scheduleVersionId: number | null): UseRoomChangeResult {
  const [phase, setPhase] = useState<RoomChangePhase>("idle");
  const [preview, setPreview] = useState<RoomChangePreview | null>(null);
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

  const requestPreview = (request: RoomChangeRequest): void => {
    if (scheduleVersionId === null || phase !== "idle") {
      return;
    }
    const versionId = scheduleVersionId;
    const isCurrent = startRequest();
    setPhase("loadingPreview");
    setPreviewError(null);
    setSaveError(null);
    Promise.all([checkScheduleVersion(versionId), callChangeRoom(versionId, request, true)])
      .then(([before, after]) => {
        if (isCurrent()) {
          setPreview({ request, before, after });
          setPhase("previewing");
        }
      })
      .catch((caught: unknown) => {
        if (isCurrent()) {
          setPreviewError(extractApiErrorMessage(caught));
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

  const confirm = async (): Promise<SavedRoomChange | null> => {
    if (scheduleVersionId === null || phase !== "previewing" || preview === null) {
      return null;
    }
    const versionId = scheduleVersionId;
    const { request } = preview;
    const isCurrent = startRequest();
    setPhase("saving");
    setSaveError(null);
    try {
      const result = await callChangeRoom(versionId, request, false);
      if (!isCurrent()) {
        return null;
      }
      setPreview(null);
      setPhase("idle");
      return { request, result };
    } catch (caught) {
      if (isCurrent()) {
        setSaveError(extractApiErrorMessage(caught));
        setPhase("previewing");
      }
      return null;
    }
  };

  return { phase, preview, previewError, saveError, requestPreview, closePreview, confirm, reset };
}
