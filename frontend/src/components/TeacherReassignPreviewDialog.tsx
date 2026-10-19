import { useId, useState, type ReactElement } from "react";
import ConfirmDialog from "./ConfirmDialog";
import ViolationDiffSummary from "./ViolationDiffSummary";
import type { TeacherReassignmentPreview } from "../hooks/useTeacherReassignment";
import {
  getViolationSentence,
  resolveClassName,
  resolveRequirementLabel,
  resolveSubjectName,
  resolveTeacherName,
  type NameLookups,
} from "../utils/failureDiagnostics";
import { diffViolations } from "../utils/violationMerge";
import { buildPreviewSummary, describeReassignLine } from "../utils/previewSummary";
import { ERROR_TEXT, PREVIEW_ACTION_LINE, PREVIEW_NOTE, PREVIEW_TOGGLE } from "../styles/ui";

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

// 「四年甲班 國語」 -- the requirement's class and subject.
function courseName(requirementId: number, lookups: NameLookups): string {
  const requirement = lookups.requirementById.get(requirementId);
  if (requirement === undefined) {
    return resolveRequirementLabel(requirementId, lookups);
  }
  return `${resolveClassName(requirement.class_id, lookups)} ${resolveSubjectName(requirement.subject_id, lookups)}`;
}

// Task 92A: the scope (docs/SYSTEM_DESIGN.md decision 17 and its known
// limitation), collapsed by default -- teachers only, this DRAFT's rows
// only, but the requirement is shared by the whole semester.
function ImpactScope(): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  return (
    <>
      <button
        type="button"
        className={PREVIEW_TOGGLE}
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={() => setExpanded((value) => !value)}
      >
        {expanded ? "收合影響範圍" : "影響範圍"}
      </button>
      {expanded && (
        <p id={panelId} className={PREVIEW_NOTE}>
          會更新這門課在排課需求中的指定教師，以及這個草稿裡這門課所有課堂的教師。同學期其他版本（包含已發布的版本）的課表不變；但排課需求由同學期所有版本共用，之後檢查那些版本可能出現「與指定教師不符」。
        </p>
      )}
    </>
  );
}

// Task 70: the 換教師 preview -- who the course goes from/to, how many
// lessons change teacher in this version, and what the change does to the
// version's problems (same before/after diff as the move/swap preview).
// Task 92A: same compact structure as the move/swap preview.
export default function TeacherReassignPreviewDialog({
  preview,
  lookups,
  isSaving,
  saveError,
  onConfirm,
  onCancel,
  restoreFocusFallback,
}: TeacherReassignPreviewDialogProps): ReactElement {
  const summary =
    preview === null
      ? null
      : buildPreviewSummary(
          diffViolations(preview.before.violations, preview.after.check.violations, (violation) =>
            getViolationSentence(violation, lookups),
          ),
        );
  // Task 90: only new ERRORs count; a new WARNING is listed but harmless.
  const addsProblems = summary !== null && summary.addsProblems;

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
      wide
    >
      {preview !== null && summary !== null && (
        <>
          <p className={PREVIEW_ACTION_LINE}>
            {describeReassignLine(
              courseName(preview.after.class_subject_requirement_id, lookups),
              preview.after.previous_teacher_id === null
                ? null
                : resolveTeacherName(preview.after.previous_teacher_id, lookups),
              resolveTeacherName(preview.after.new_teacher_id, lookups),
              preview.after.updated_schedule_row_count,
            )}
          </p>
          <ViolationDiffSummary summary={summary} changeNoun="換人" />
          <p className={PREVIEW_NOTE}>只換教師，不動時段與教室；確認後立即儲存，無法復原</p>
          <ImpactScope />
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
