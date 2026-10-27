import type { ReactElement, ReactNode } from "react";
import { badgeClass, type BadgeTone } from "../utils/badgeTone";
import { formatRecordStatus, recordStatusTone } from "../utils/scheduleVersionFormat";
import type { ScheduleVersion } from "../types/scheduleVersion";

// Task 98: the one status pill -- light background, dark text, a tone
// from utils/badgeTone.ts. Never color alone: the text always says it.
export default function StatusBadge({
  tone,
  className,
  title,
  children,
}: {
  tone: BadgeTone;
  // Spacing only (e.g. "ml-2"); the colors come from the tone.
  className?: string;
  title?: string;
  children: ReactNode;
}): ReactElement {
  return (
    <span className={className === undefined ? badgeClass(tone) : `${badgeClass(tone)} ${className}`} title={title}>
      {children}
    </span>
  );
}

// A 排課紀錄's status: 「已發布」, 「自動排課」, 「手動排課」, 「尚未排課」...
export function RecordStatusBadge({
  record,
}: {
  record: Pick<ScheduleVersion, "status" | "is_published" | "copied_from_display_number">;
}): ReactElement {
  return <StatusBadge tone={recordStatusTone(record)}>{formatRecordStatus(record)}</StatusBadge>;
}
