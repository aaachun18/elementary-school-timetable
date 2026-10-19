import type { ReactElement } from "react";
import ConfirmDialog from "./ConfirmDialog";
import PreviewChangeList from "./PreviewChangeList";
import ViolationDiffSummary from "./ViolationDiffSummary";
import type { RoomChangePreview } from "../hooks/useRoomChange";
import {
  getViolationSentence,
  resolveTimeSlotLabel,
  type NameLookups,
} from "../utils/failureDiagnostics";
import { buildPreviewSummary } from "../utils/previewSummary";
import { describeRoomChangeLine, roomChangeLines } from "../utils/roomChange";
import { diffViolations } from "../utils/violationMerge";
import { ERROR_TEXT, MUTED_TEXT, PREVIEW_ACTION_LINE, PREVIEW_NOTE } from "../styles/ui";

interface RoomChangePreviewDialogProps {
  // null = closed.
  preview: RoomChangePreview | null;
  lookups: NameLookups;
  isSaving: boolean;
  saveError: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  // Task 85: see ConfirmDialog's prop of the same name.
  restoreFocusFallback?: () => void;
}

// Task 95: the 「更改教室」 preview -- the same compact structure as the
// move/swap and placement previews (Task 92A): what changes, the verdict
// and problem lines (compared by identity), the changed rows, one note.
// No change at all (every row already in that room): 「沒有任何變動」 and
// only 「關閉」, like a move to the same slot.
export default function RoomChangePreviewDialog({
  preview,
  lookups,
  isSaving,
  saveError,
  onConfirm,
  onCancel,
  restoreFocusFallback,
}: RoomChangePreviewDialogProps): ReactElement {
  const summary =
    preview === null
      ? null
      : buildPreviewSummary(
          diffViolations(preview.before.violations, preview.after.check.violations, (violation) =>
            getViolationSentence(violation, lookups),
          ),
        );
  const addsProblems = summary !== null && summary.addsProblems;
  const hasChanges = preview !== null && preview.after.changes.length > 0;
  const roomName = (roomId: number | null): string | null =>
    roomId === null ? null : (lookups.roomById.get(roomId)?.name ?? `教室 ID ${roomId}`);

  return (
    <ConfirmDialog
      open={preview !== null}
      title="預覽更改教室"
      confirmLabel={addsProblems ? "仍要更改" : "確認更改"}
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
          {!hasChanges ? (
            <>
              <p className={PREVIEW_ACTION_LINE}>
                {preview.request.lesson.className} {preview.request.lesson.subjectName}：教室{" "}
                {roomName(preview.request.roomId) ?? "無"}
              </p>
              <p className={MUTED_TEXT}>沒有任何變動，教室已經是這一間</p>
            </>
          ) : (
            <>
              <p className={PREVIEW_ACTION_LINE}>
                {describeRoomChangeLine(
                  `${preview.request.lesson.className} ${preview.request.lesson.subjectName}`,
                  preview.after.changes,
                  roomName,
                )}
              </p>
              {preview.after.changes.length > 1 && (
                <PreviewChangeList
                  lines={roomChangeLines(
                    preview.after.changes,
                    (id) => resolveTimeSlotLabel(id, lookups),
                    roomName,
                  )}
                />
              )}
              <ViolationDiffSummary summary={summary} changeNoun="更改" />
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
