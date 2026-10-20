import { describe, expect, it } from "vitest";
import { sortRecords } from "./scheduleRecords";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";

function version(id: number, semesterId: number, versionNumber: number): ScheduleVersion {
  return { id, semester_id: semesterId, version_number: versionNumber } as ScheduleVersion;
}

function semester(id: number, academicYearId: number, number: number): Semester {
  return { id, academic_year_id: academicYearId, number } as Semester;
}

describe("sortRecords", () => {
  it("lists the newest year, then the later semester, then the newest version first", () => {
    const semesters = new Map([
      [1, semester(1, 10, 1)],
      [2, semester(2, 10, 2)],
      [3, semester(3, 11, 1)],
    ]);
    const years = new Map([
      [10, 114],
      [11, 115],
    ]);
    const versions = [version(1, 1, 1), version(2, 2, 1), version(3, 3, 1), version(4, 2, 2)];

    expect(sortRecords(versions, semesters, years).map((v) => v.id)).toEqual([3, 4, 2, 1]);
  });
});
