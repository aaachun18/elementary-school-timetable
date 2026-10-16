import type { ReactElement } from "react";
import ConfirmDialog from "./ConfirmDialog";
import ViolationDiffSummary from "./ViolationDiffSummary";
import type { TeacherReassignmentPreview } from "../hooks/useTeacherReassignment";
import {
  getViolationSentence,
  resolveRequirementLabel,
  resolveTeacherName,
  type NameLookups,
} from "../utils/failureDiagnostics";
import { diffViolations, splitBySeverity } from "../utils/violationMerge";
import { ERROR_TEXT, MUTED_TEXT } from "../styles/ui";

interface TeacherReassignPreviewDialogProps {
  // null = closed.
  preview: TeacherReassignmentPreview | null;
  lookups: NameLookups;
  isSaving: boolean;
  saveError: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  // Task 86: see ConfirmDialog's prop of the same name.
  restoreFocusFallback?: () => void;
}

// Task 70: the 換教師 preview -- who the course goes from/to, how many
// lessons change teacher in this version, and what the change does to the
// version's problems (same before/after diff as the move/swap preview).
export default function TeacherReassignPreviewDialog({
  preview,
  lookups,
  isSaving,
  saveError,
  onConfirm,
  onCancel,
  restoreFocusFallback,
}: TeacherReassignPreviewDialogProps): ReactElement {
  const diff =
    preview === null
      ? null
      : diffViolations(preview.before.violations, preview.after.check.violations, (violation) =>
          getViolationSentence(violation, lookups),
        );
  // Task 90: only new ERRORs count; a new WARNING is listed but harmless.
  const addsProblems = diff !== null && splitBySeverity(diff.added).errors.length > 0;

  return (
    <ConfirmDialog
      open={preview !== null}
      title="預覽換教師"
      confirmLabel={addsProblems ? "仍要換教師" : "確認換教師"}
      cancelLabel="返回"
      danger={addsProblems}
      busy={isSaving}
      busyLabel="儲存中…"
      onConfirm={onConfirm}
      onCancel={onCancel}
      restoreFocusFallback={restoreFocusFallback}
    >
      {preview !== null && diff !== null && (
        <>
          <p className="font-medium text-gray-900">
            「{resolveRequirementLabel(preview.after.class_subject_requirement_id, lookups)}」：
            {preview.after.previous_teacher_id === null
              ? "未指定教師"
              : resolveTeacherName(preview.after.previous_teacher_id, lookups)}
            {" → "}
            {resolveTeacherName(preview.after.new_teacher_id, lookups)}
          </p>
          <p className="text-sm text-gray-700">
            {preview.after.updated_schedule_row_count > 0
              ? `這個版本中有 ${preview.after.updated_schedule_row_count} 堂課會改由${resolveTeacherName(
                  preview.after.new_teacher_id,
                  lookups,
                )}授課。`
              : "這個版本中沒有課堂需要改變教師（可能尚未排課，或已經是這位教師），只會更新排課需求的指定教師。"}
          </p>
          <ViolationDiffSummary diff={diff} lookups={lookups} changeNoun="換人" />
          {addsProblems && (
            <p className={ERROR_TEXT}>
              這次換人會新增上面的問題。系統不會阻擋，仍可確認儲存，之後再另行調整。
            </p>
          )}
          {/* Scope, as stated in docs/SYSTEM_DESIGN.md decision 17 and its
              known limitation: teachers only, this DRAFT's rows only, but
              the requirement is shared by the whole semester. */}
          <p className={MUTED_TEXT}>
            影響範圍：只換教師，不移動任何節次或教室。會同時更新這門課在排課需求中的指定教師，以及這個草稿裡這門課所有課堂的教師；同學期其他版本（包含已發布的版本）的課表不會改變，但排課需求是同學期所有版本共用的，之後檢查那些版本可能會出現「與指定教師不符」。確認後立即儲存，沒有復原功能。
          </p>
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
