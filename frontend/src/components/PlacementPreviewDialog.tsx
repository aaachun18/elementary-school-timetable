import type { ReactElement } from "react";
import ConfirmDialog from "./ConfirmDialog";
import PreviewChangeList from "./PreviewChangeList";
import ViolationDiffSummary from "./ViolationDiffSummary";
import type { PlacementPreview } from "../hooks/usePlacement";
import {
  getViolationSentence,
  resolveTimeSlotLabel,
  type NameLookups,
} from "../utils/failureDiagnostics";
import { describePlaceLine, firstPlacedSlot, placementChangeLines } from "../utils/placement";
import { buildPreviewSummary } from "../utils/previewSummary";
import { diffViolations } from "../utils/violationMerge";
import { ERROR_TEXT, PREVIEW_ACTION_LINE, PREVIEW_NOTE } from "../styles/ui";

interface PlacementPreviewDialogProps {
  // null = closed.
  preview: PlacementPreview | null;
  lookups: NameLookups;
  isSaving: boolean;
  saveError: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  // Task 85: see ConfirmDialog's prop of the same name.
  restoreFocusFallback?: () => void;
}

// Task 93: the preview of placing an unscheduled card -- the same compact
// structure as the move/swap preview (Task 92A): one line of what is
// placed, the verdict and problem lines, the rows of a block, one note.
// The problems are compared by identity (violationIdentityKey), never by
// schedule_id: a preview's new rows don't have one yet.
export default function PlacementPreviewDialog({
  preview,
  lookups,
  isSaving,
  saveError,
  onConfirm,
  onCancel,
  restoreFocusFallback,
}: PlacementPreviewDialogProps): ReactElement {
  const summary =
    preview === null
      ? null
      : buildPreviewSummary(
          diffViolations(preview.before.violations, preview.after.check.violations, (violation) =>
            getViolationSentence(violation, lookups),
          ),
        );
  const addsProblems = summary !== null && summary.addsProblems;

  return (
    <ConfirmDialog
      open={preview !== null}
      title="預覽放入"
      confirmLabel={addsProblems ? "仍要放入" : "確認放入"}
      cancelLabel="返回"
      danger={addsProblems}
      busy={isSaving}
      busyLabel="儲存中…"
      onConfirm={onConfirm}
      onCancel={onCancel}
      restoreFocusFallback={restoreFocusFallback}
      wide
    >
      {preview !== null && summary !== null && (
        <>
          <p className={PREVIEW_ACTION_LINE}>
            {describePlaceLine(
              `${preview.request.card.className} ${preview.request.card.subjectName}`,
              resolveTimeSlotLabel(
                firstPlacedSlot(preview.after.changes, preview.request.card.lessonIds) ??
                  preview.request.timeSlotId,
                lookups,
              ),
              preview.after.changes.length,
            )}
          </p>
          {preview.after.changes.length > 1 && (
            <PreviewChangeList
              lines={placementChangeLines(preview.after.changes, preview.request.card.lessonIds, (id) =>
                resolveTimeSlotLabel(id, lookups),
              )}
            />
          )}
          <ViolationDiffSummary summary={summary} changeNoun="放入" />
          <p className={PREVIEW_NOTE}>確認後立即儲存，無法復原</p>
          {saveError !== null && (
            <p role="alert" className={ERROR_TEXT}>
              {saveError}
            </p>
          )}
        </>
      )}
    </ConfirmDialog>
  );
}
