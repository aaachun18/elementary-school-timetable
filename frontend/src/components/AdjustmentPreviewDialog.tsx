import type { ReactElement } from "react";
import ConfirmDialog from "./ConfirmDialog";
import ViolationDiffSummary from "./ViolationDiffSummary";
import type { AdjustmentPreview, LessonAdjustment } from "../hooks/useLessonAdjustment";
import type { EnrichedSchedule } from "../hooks/useTimetableData";
import {
  getViolationSentence,
  resolveTimeSlotLabel,
  type NameLookups,
} from "../utils/failureDiagnostics";
import { diffViolations } from "../utils/violationMerge";
import { ERROR_TEXT, MUTED_TEXT } from "../styles/ui";

interface AdjustmentPreviewDialogProps {
  // null = closed.
  preview: AdjustmentPreview | null;
  lookups: NameLookups;
  isSaving: boolean;
  saveError: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  // Task 85: see ConfirmDialog's prop of the same name.
  restoreFocusFallback?: () => void;
}

function lessonName(lesson: EnrichedSchedule): string {
  return `${lesson.className} ${lesson.subjectName}`;
}

// The plain-language one-liner at the top of the dialog.
function describeAdjustment(adjustment: LessonAdjustment, lookups: NameLookups): string {
  const { lesson } = adjustment;
  const currentSlot = resolveTimeSlotLabel(lesson.timeSlotId, lookups);
  if (adjustment.kind === "move") {
    return `把「${lessonName(lesson)}」從 ${currentSlot} 移到 ${resolveTimeSlotLabel(
      adjustment.targetTimeSlotId,
      lookups,
    )}`;
  }
  const otherSlot = resolveTimeSlotLabel(adjustment.other.timeSlotId, lookups);
  return `把「${lessonName(lesson)}」（${currentSlot}）與「${lessonName(
    adjustment.other,
  )}」（${otherSlot}）的時段對調`;
}

// Task 69: the move/swap preview -- what THIS change does to the version's
// problems (ViolationDiffSummary), not the whole "after" check.
export default function AdjustmentPreviewDialog({
  preview,
  lookups,
  isSaving,
  saveError,
  onConfirm,
  onCancel,
  restoreFocusFallback,
}: AdjustmentPreviewDialogProps): ReactElement {
  const isMove = preview?.adjustment.kind === "move";
  const verb = isMove ? "移動" : "對調";
  const hasChanges = preview !== null && preview.after.changes.length > 0;
  const diff =
    preview === null
      ? null
      : diffViolations(preview.before.violations, preview.after.check.violations, (violation) =>
          getViolationSentence(violation, lookups),
        );
  const addsProblems = diff !== null && diff.added.length > 0;

  return (
    <ConfirmDialog
      open={preview !== null}
      title={`預覽${verb}`}
      confirmLabel={addsProblems ? `仍要${verb}` : `確認${verb}`}
      cancelLabel={hasChanges ? "返回" : "關閉"}
      danger={addsProblems}
      busy={isSaving}
      busyLabel="儲存中…"
      showConfirm={hasChanges}
      onConfirm={onConfirm}
      onCancel={onCancel}
      restoreFocusFallback={restoreFocusFallback}
    >
      {preview !== null && diff !== null && (
        <>
          <p className="font-medium text-gray-900">{describeAdjustment(preview.adjustment, lookups)}</p>
          {!hasChanges ? (
            <p className={MUTED_TEXT}>沒有任何變動。</p>
          ) : (
            <>
              <ViolationDiffSummary diff={diff} lookups={lookups} changeNoun="異動" />
              <p className={MUTED_TEXT}>
                {isMove ? "只會改變這堂課的時段，老師與教室不變。" : "只會交換兩堂課的時段，老師與教室各自不變。"}
                確認後立即儲存，沒有復原功能。
              </p>
            </>
          )}
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
