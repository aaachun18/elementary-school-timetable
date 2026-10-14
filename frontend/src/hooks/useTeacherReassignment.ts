import { useEffect, useRef, useState } from "react";
import { check as checkScheduleVersion, reassignTeacher } from "../api/scheduleVersions";
import { extractApiErrorMessage } from "../constants/errorMessages";
import type { ScheduleCheckResult, TeacherReassignmentResult } from "../types/scheduler";

// One reassignment the user picked in the panel, not yet saved.
export interface TeacherReassignmentChoice {
  requirementId: number;
  newTeacherId: number;
}

export interface TeacherReassignmentPreview {
  choice: TeacherReassignmentChoice;
  // GET check right before the preview: the version as it is now.
  before: ScheduleCheckResult;
  // The same reassignment with dry_run: what saving it would do.
  after: TeacherReassignmentResult;
}

// Same phases as useLessonAdjustment.
export type ReassignmentPhase = "idle" | "loadingPreview" | "previewing" | "saving";

interface UseTeacherReassignmentResult {
  phase: ReassignmentPhase;
  preview: TeacherReassignmentPreview | null;
  // The preview requests failed; the reassignment was dropped.
  previewError: string | null;
  // Saving failed; shown inside the still-open preview dialog.
  saveError: string | null;
  requestPreview: (choice: TeacherReassignmentChoice) => void;
  closePreview: () => void;
  // Resolves with what was saved, or null if it failed / was superseded.
  confirm: () => Promise<TeacherReassignmentResult | null>;
  reset: () => void;
}

// Task 70: pick -> preview (before check + dry_run) -> confirm, for the
// 換教師 panel. Modelled on useLessonAdjustment: one request in flight at a
// time; a response arriving after reset() or unmount is dropped; a failed
// preview leaves nothing half-done behind.
export function useTeacherReassignment(
  scheduleVersionId: number | null,
): UseTeacherReassignmentResult {
  const [phase, setPhase] = useState<ReassignmentPhase>("idle");
  const [preview, setPreview] = useState<TeacherReassignmentPreview | null>(null);
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

  const requestPreview = (choice: TeacherReassignmentChoice): void => {
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
      reassignTeacher(versionId, { ...choice, dryRun: true }),
    ])
      .then(([before, after]) => {
        if (isCurrent()) {
          setPreview({ choice, before, after });
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

  const confirm = async (): Promise<TeacherReassignmentResult | null> => {
    if (scheduleVersionId === null || phase !== "previewing" || preview === null) {
      return null;
    }
    const versionId = scheduleVersionId;
    const { choice } = preview;
    const isCurrent = startRequest();
    setPhase("saving");
    setSaveError(null);
    try {
      const result = await reassignTeacher(versionId, { ...choice, dryRun: false });
      if (!isCurrent()) {
        return null;
      }
      setPreview(null);
      setPhase("idle");
      return result;
    } catch (caught) {
      // 404/409 included: the dialog stays open with the message.
      if (isCurrent()) {
        setSaveError(extractApiErrorMessage(caught));
        setPhase("previewing");
      }
      return null;
    }
  };

  return { phase, preview, previewError, saveError, requestPreview, closePreview, confirm, reset };
}
