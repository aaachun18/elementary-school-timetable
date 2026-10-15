import { describe, expect, it } from "vitest";
import type { ScheduleVersion, ScheduleVersionStatus } from "../types/scheduleVersion";
import {
  PUBLISHED_DELETE_HINT,
  canDeleteVersion,
  deleteWarningOf,
  pickVersionAfterDelete,
} from "./versionDelete";

function version(
  id: number,
  semesterId: number,
  versionNumber: number,
  status: ScheduleVersionStatus,
): ScheduleVersion {
  return {
    id,
    semester_id: semesterId,
    version_number: versionNumber,
    status,
    created_at: "",
    updated_at: "",
  };
}

describe("canDeleteVersion", () => {
  it("allows DRAFT and ARCHIVED", () => {
    expect(canDeleteVersion("DRAFT")).toBe(true);
    expect(canDeleteVersion("ARCHIVED")).toBe(true);
  });

  it("refuses PUBLISHED and anything unknown", () => {
    expect(canDeleteVersion("PUBLISHED")).toBe(false);
    expect(canDeleteVersion("SOMETHING_NEW")).toBe(false);
  });

  it("uses the backend's wording for the PUBLISHED hint", () => {
    expect(PUBLISHED_DELETE_HINT).toBe("已發布的版本無法刪除，請先取消發布");
  });
});

describe("deleteWarningOf", () => {
  it("warns that an ARCHIVED version can no longer be switched back to", () => {
    expect(deleteWarningOf("ARCHIVED")).toBe("刪除後無法復原，也無法再切換回這個版本。");
  });

  it("gives a DRAFT the plain warning", () => {
    expect(deleteWarningOf("DRAFT")).toBe("刪除後無法復原。");
  });
});

describe("pickVersionAfterDelete", () => {
  const deleted = version(4, 13, 4, "ARCHIVED");

  it("prefers the semester's PUBLISHED version", () => {
    const remaining = [
      version(5, 13, 5, "ARCHIVED"),
      version(11, 13, 11, "PUBLISHED"),
      version(12, 13, 12, "DRAFT"),
    ];

    expect(pickVersionAfterDelete(remaining, deleted)?.id).toBe(11);
  });

  it("otherwise picks the newest version of the semester", () => {
    const remaining = [
      version(12, 13, 12, "DRAFT"),
      version(5, 13, 5, "ARCHIVED"),
      version(8, 13, 8, "ARCHIVED"),
    ];

    expect(pickVersionAfterDelete(remaining, deleted)?.id).toBe(12);
  });

  it("ignores other semesters, even a PUBLISHED one", () => {
    const remaining = [version(20, 99, 1, "PUBLISHED"), version(5, 13, 5, "DRAFT")];

    expect(pickVersionAfterDelete(remaining, deleted)?.id).toBe(5);
  });

  it("returns null when the semester has no other version", () => {
    expect(pickVersionAfterDelete([version(20, 99, 1, "PUBLISHED")], deleted)).toBeNull();
    expect(pickVersionAfterDelete([], deleted)).toBeNull();
  });

  it("never returns the deleted version even if the list still has it", () => {
    const stale = [deleted, version(5, 13, 5, "ARCHIVED")];

    expect(pickVersionAfterDelete(stale, deleted)?.id).toBe(5);
  });
});
