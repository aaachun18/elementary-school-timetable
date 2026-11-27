// v3: the order of the 排課紀錄 list -- by 編號, newest (highest) first,
// whatever the semester: the last one made is always on top. Pure, no
// React.

import type { ScheduleVersion } from "../types/scheduleVersion";

export function sortRecords(versions: readonly ScheduleVersion[]): ScheduleVersion[] {
  return [...versions].sort(
    (a, b) => (b.version_number ?? 0) - (a.version_number ?? 0) || b.id - a.id,
  );
}
