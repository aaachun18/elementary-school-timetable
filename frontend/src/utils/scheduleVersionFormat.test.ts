import { describe, expect, it } from "vitest";
import {
  formatRecordStatus,
  formatSemesterLabel,
  formatStatusOnly,
  formatVersionLabel,
  hasTimetable,
  recordStatusTone,
} from "./scheduleVersionFormat";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";

function record(fields: Partial<ScheduleVersion> = {}): ScheduleVersion {
  return {
    id: 24,
    semester_id: 3,
    version_number: 4,
    display_number: 2,
    status: "AUTO",
    is_published: false,
    copied_from_number: null,
    copied_from_display_number: null,
    editing_source_id: null,
    note: null,
    created_at: "",
    updated_at: "",
    ...fields,
  };
}

describe("formatRecordStatus", () => {
  it.each([
    ["NOT_SCHEDULED", "尚未排課"],
    ["AUTO", "自動排課"],
    ["MANUAL", "手動排課"],
    ["EDITING", "編輯中"],
  ] as const)("%s -> %s", (status, label) => {
    expect(formatRecordStatus(record({ status }))).toBe(label);
  });

  it("names the record a copy came from by its 編號 now, not its serial", () => {
    expect(
      formatRecordStatus(record({ status: "COPIED", copied_from_number: 3, copied_from_display_number: 5 })),
    ).toBe("複製自編號 5");
  });

  it("says only 複製 once the source record has been deleted", () => {
    expect(
      formatRecordStatus(record({ status: "COPIED", copied_from_number: 3, copied_from_display_number: null })),
    ).toBe("複製");
  });

  it("shows 已發布 for the published record, whatever its own status", () => {
    expect(formatRecordStatus(record({ status: "MANUAL", is_published: true }))).toBe("已發布");
    expect(formatStatusOnly(record({ status: "MANUAL", is_published: true }))).toBe("手動排課");
  });

  it("shows an unknown status as its raw string, never as a known label", () => {
    expect(formatStatusOnly({ status: "SOMETHING_NEW" as ScheduleVersion["status"], copied_from_display_number: null })).toBe(
      "SOMETHING_NEW",
    );
    expect(formatStatusOnly({ status: "toString" as ScheduleVersion["status"], copied_from_display_number: null })).toBe(
      "toString",
    );
  });
});

describe("recordStatusTone", () => {
  it("is green when published, amber when not scheduled, blue / violet with a timetable", () => {
    expect(recordStatusTone(record({ is_published: true }))).toBe("success");
    expect(recordStatusTone(record({ status: "NOT_SCHEDULED" }))).toBe("warning");
    expect(recordStatusTone(record({ status: "AUTO" }))).toBe("info");
    expect(recordStatusTone(record({ status: "MANUAL" }))).toBe("manual");
    expect(recordStatusTone(record({ status: "COPIED" }))).toBe("neutral");
  });

  it("is success for a published record whatever its status", () => {
    expect(recordStatusTone(record({ status: "MANUAL", is_published: true }))).toBe("success");
  });

  it("is neutral for 編輯中 and for an unknown status", () => {
    expect(recordStatusTone(record({ status: "EDITING" }))).toBe("neutral");
    expect(recordStatusTone(record({ status: "SOMETHING_NEW" as ScheduleVersion["status"] }))).toBe("neutral");
    expect(recordStatusTone(record({ status: "toString" as ScheduleVersion["status"] }))).toBe("neutral");
  });
});

describe("hasTimetable", () => {
  it("is true for 自動排課, 手動排課 and copies only", () => {
    expect(["AUTO", "MANUAL", "COPIED"].map(hasTimetable)).toEqual([true, true, true]);
    expect(["NOT_SCHEDULED", "EDITING", "toString"].map(hasTimetable)).toEqual([false, false, false]);
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

  it("reads 「編號 {n}・{學期}（{狀態}）」", () => {
    expect(formatVersionLabel(record({ is_published: true }), new Map([[3, semester]]), new Map([[1, 115]]))).toBe(
      "編號 2・115 學年度第 1 學期（已發布）",
    );
  });

  it("falls back to ids when the semester or academic year is unknown", () => {
    expect(formatVersionLabel(record({ status: "NOT_SCHEDULED" }), new Map(), new Map())).toBe(
      "編號 2・學期 ID 3（尚未排課）",
    );
    expect(formatSemesterLabel(semester, new Map())).toBe("學期 ID 3");
  });
});
