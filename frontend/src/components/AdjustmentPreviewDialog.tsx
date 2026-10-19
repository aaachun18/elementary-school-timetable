import type { ReactElement } from "react";
import ConfirmDialog from "./ConfirmDialog";
import PreviewChangeList from "./PreviewChangeList";
import ViolationDiffSummary from "./ViolationDiffSummary";
import type { AdjustmentPreview, LessonAdjustment } from "../hooks/useLessonAdjustment";
import type { EnrichedSchedule } from "../hooks/useTimetableData";
import {
  getViolationSentence,
  resolveTimeSlotLabel,
  type NameLookups,
} from "../utils/failureDiagnostics";
import { diffViolations } from "../utils/violationMerge";
import { buildPreviewSummary, describeMoveLine, describeSwapLine } from "../utils/previewSummary";
import type { ScheduleChangeDetail } from "../types/scheduler";
import { ERROR_TEXT, MUTED_TEXT, PREVIEW_ACTION_LINE, PREVIEW_NOTE } from "../styles/ui";

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

// Task 92A: the one 「這次會做什麼」 line (utils/previewSummary.ts).
function describeAdjustment(
  adjustment: LessonAdjustment,
  changes: readonly ScheduleChangeDetail[],
  lookups: NameLookups,
): string {
  const { lesson } = adjustment;
  const currentSlot = resolveTimeSlotLabel(lesson.timeSlotId, lookups);
  if (adjustment.kind === "move") {
    return describeMoveLine(
      lessonName(lesson),
      currentSlot,
      resolveTimeSlotLabel(adjustment.targetTimeSlotId, lookups),
      changes.length,
    );
  }
  return describeSwapLine(
    lessonName(lesson),
    currentSlot,
    lessonName(adjustment.other),
    resolveTimeSlotLabel(adjustment.other.timeSlotId, lookups),
    changes.length,
  );
}

// Task 90: a lesson block (連堂) moves or swaps as a whole -- the backend's
// `changes` then list more rows than the one (move) or two (swap) lessons
// picked.
function isBlockChange(adjustment: LessonAdjustment, changes: readonly ScheduleChangeDetail[]): boolean {
  return changes.length > (adjustment.kind === "move" ? 1 : 2);
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
// problems, not the whole "after" check. Task 92A: title, one line of what
// changes, one verdict line, the problem lines, one footnote, buttons.
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
  const summary =
    preview === null
      ? null
      : buildPreviewSummary(
          diffViolations(preview.before.violations, preview.after.check.violations, (violation) =>
            getViolationSentence(violation, lookups),
          ),
        );
  // Task 90: only new ERRORs make this a 「仍要…」 change.
  const addsProblems = summary !== null && summary.addsProblems;
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
      wide
    >
      {preview !== null && summary !== null && (
        <>
          <p className={PREVIEW_ACTION_LINE}>
            {describeAdjustment(preview.adjustment, preview.after.changes, lookups)}
          </p>
          {isBlockChange(preview.adjustment, preview.after.changes) && (
            <PreviewChangeList
              lines={preview.after.changes.map((change) => describeChange(change, scheduleById, lookups))}
            />
          )}
          {!hasChanges ? (
            <p className={MUTED_TEXT}>沒有任何變動。</p>
          ) : (
            <>
              <ViolationDiffSummary summary={summary} changeNoun="異動" />
              <p className={PREVIEW_NOTE}>確認後立即儲存，無法復原</p>
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
