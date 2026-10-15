import { describe, expect, it } from "vitest";
import {
  formatSemesterLabel,
  formatVersionLabel,
  formatVersionStatus,
  versionStatusBadgeClass,
} from "./scheduleVersionFormat";
import { BADGE_INFO, BADGE_NEUTRAL, BADGE_SUCCESS } from "../styles/ui";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";

describe("formatVersionStatus", () => {
  it.each([
    ["DRAFT", "草稿"],
    ["PUBLISHED", "已發布"],
    ["ARCHIVED", "已封存"],
  ])("%s -> %s", (status, label) => {
    expect(formatVersionStatus(status)).toBe(label);
  });

  it("shows an unknown status as its raw string, never as a known label", () => {
    expect(formatVersionStatus("SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });

  it("does not treat inherited object keys as statuses", () => {
    expect(formatVersionStatus("toString")).toBe("toString");
  });
});

describe("versionStatusBadgeClass", () => {
  it("uses a distinct badge per known status and the neutral one otherwise", () => {
    expect(versionStatusBadgeClass("DRAFT")).toBe(BADGE_INFO);
    expect(versionStatusBadgeClass("PUBLISHED")).toBe(BADGE_SUCCESS);
    expect(versionStatusBadgeClass("ARCHIVED")).toBe(BADGE_NEUTRAL);
    expect(versionStatusBadgeClass("SOMETHING_NEW")).toBe(BADGE_NEUTRAL);
  });
});

describe("formatVersionLabel", () => {
  const semester: Semester = {
    id: 3,
    academic_year_id: 1,
    number: 1,
    is_active: true,
    created_at: "",
    updated_at: "",
  };
  const version = (status: ScheduleVersion["status"]): ScheduleVersion => ({
    id: 24,
    semester_id: 3,
    version_number: 4,
    status,
    created_at: "",
    updated_at: "",
  });

  it("reads 「{學期} v{版本號}（{狀態}）」", () => {
    expect(formatVersionLabel(version("PUBLISHED"), new Map([[3, semester]]), new Map([[1, 1]]))).toBe(
      "1 學年度第 1 學期 v4（已發布）",
    );
  });

  it("falls back to ids when the semester or academic year is unknown", () => {
    expect(formatVersionLabel(version("DRAFT"), new Map(), new Map())).toBe("學期 ID 3 v4（草稿）");
    expect(formatSemesterLabel(semester, new Map())).toBe("學期 ID 3");
  });
});
