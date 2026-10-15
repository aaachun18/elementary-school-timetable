// Task 80: which versions can be deleted, and what the console shows after a
// delete. Mirrors the backend rule (services/schedule_version.py's
// delete_schedule_version()): DRAFT and ARCHIVED can be deleted, the
// semester's PUBLISHED version cannot -- it has to be unpublished first.
// The backend still decides; this only drives what the page offers.

import type { ScheduleVersion } from "../types/scheduleVersion";

// Same wording as the backend's 409, shown next to the hidden button.
export const PUBLISHED_DELETE_HINT = "已發布的版本無法刪除，請先取消發布";

// Plain string, so an unexpected status from the backend is never offered
// a delete it might not support.
export function canDeleteVersion(status: string): boolean {
  return status === "DRAFT" || status === "ARCHIVED";
}

// What the delete dialog warns about, per status. ARCHIVED: deleting also
// removes the option of switching back to it later.
export function deleteWarningOf(status: string): string {
  return status === "ARCHIVED"
    ? "刪除後無法復原，也無法再切換回這個版本。"
    : "刪除後無法復原。";
}

// After `deleted` is gone, the version the console switches to: another
// version of the same semester -- its PUBLISHED one if any, otherwise the
// newest (highest version_number). null when the semester has no other
// version left (the page then goes back to the version picker).
export function pickVersionAfterDelete(
  remaining: readonly ScheduleVersion[],
  deleted: Pick<ScheduleVersion, "id" | "semester_id">,
): ScheduleVersion | null {
  const sameSemester = remaining.filter(
    (version) => version.semester_id === deleted.semester_id && version.id !== deleted.id,
  );
  const published = sameSemester.find((version) => version.status === "PUBLISHED");
  if (published !== undefined) {
    return published;
  }
  let newest: ScheduleVersion | null = null;
  for (const version of sameSemester) {
    if (newest === null || version.version_number > newest.version_number) {
      newest = version;
    }
  }
  return newest;
}
