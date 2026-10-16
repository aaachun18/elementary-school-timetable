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
import { diffViolations, splitBySeverity } from "../utils/violationMerge";
import type { ScheduleChangeDetail } from "../types/scheduler";
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
  // Task 90: the timetable's lessons, to name every row a lesson block
  // (連堂) change moves.
  schedules: readonly EnrichedSchedule[];
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

// Task 90: a lesson block (連堂) moves or swaps as a whole -- the backend's
// `changes` then list more rows than the one (move) or two (swap) lessons
// picked. The short line under the description says so; null otherwise.
function describeBlockChange(
  adjustment: LessonAdjustment,
  changes: readonly ScheduleChangeDetail[],
): string | null {
  if (adjustment.kind === "move") {
    return changes.length > 1 ? `整組 ${changes.length} 節一起移動` : null;
  }
  return changes.length > 2 ? `兩組連堂整組對調，共 ${changes.length} 節` : null;
}

// Every changed row as 「{班級} {科目}：{原時段} → {新時段}」.
function describeChange(
  change: ScheduleChangeDetail,
  scheduleById: ReadonlyMap<number, EnrichedSchedule>,
  lookups: NameLookups,
): string {
  const lesson = scheduleById.get(change.schedule_id);
  const name = lesson === undefined ? "這堂課" : lessonName(lesson);
  return `${name}：${resolveTimeSlotLabel(change.previous_time_slot_id, lookups)} → ${resolveTimeSlotLabel(
    change.new_time_slot_id,
    lookups,
  )}`;
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
  schedules,
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
  // Task 90: only new ERRORs make this a 「仍要…」 change.
  const addsProblems = diff !== null && splitBySeverity(diff.added).errors.length > 0;
  const blockChange =
    preview === null ? null : describeBlockChange(preview.adjustment, preview.after.changes);
  const scheduleById = new Map(schedules.map((schedule) => [schedule.scheduleId, schedule]));

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
          {blockChange !== null && (
            <div className="text-sm text-gray-700">
              <p className="font-medium text-indigo-800">{blockChange}：</p>
              <ul className="m-0 list-none p-0">
                {preview.after.changes.map((change) => (
                  <li key={change.schedule_id}>{describeChange(change, scheduleById, lookups)}</li>
                ))}
              </ul>
            </div>
          )}
          {!hasChanges ? (
            <p className={MUTED_TEXT}>沒有任何變動。</p>
          ) : (
            <>
              <ViolationDiffSummary diff={diff} lookups={lookups} changeNoun="異動" />
              <p className={MUTED_TEXT}>
                {blockChange !== null
                  ? "連堂整組一起異動，老師與教室各自不變。"
                  : isMove
                    ? "只會改變這堂課的時段，老師與教室不變。"
                    : "只會交換兩堂課的時段，老師與教室各自不變。"}
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
