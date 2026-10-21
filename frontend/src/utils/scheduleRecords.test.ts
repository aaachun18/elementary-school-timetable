import { describe, expect, it } from "vitest";
import { sortRecords } from "./scheduleRecords";
import type { ScheduleVersion } from "../types/scheduleVersion";

function record(id: number, semesterId: number, versionNumber: number): ScheduleVersion {
  return { id, semester_id: semesterId, version_number: versionNumber } as ScheduleVersion;
}

describe("sortRecords", () => {
  it("lists the newest 編號 first, whatever the semester", () => {
    const records = [record(1, 1, 1), record(2, 2, 2), record(3, 1, 4), record(4, 3, 3)];

    expect(sortRecords(records).map((r) => r.id)).toEqual([3, 4, 2, 1]);
  });
});
