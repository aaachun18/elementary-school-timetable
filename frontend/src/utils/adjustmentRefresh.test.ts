import { describe, expect, it } from "vitest";
import { isLocatedProblemGone, planAdjustmentRefresh } from "./adjustmentRefresh";
import { violationIdentityKey } from "./violationMerge";
import type { ConstraintViolationDetail } from "../types/scheduler";

function violation(fields: Partial<ConstraintViolationDetail>): ConstraintViolationDetail {
  return {
    type: "ROOM_MISSING_FOR_TYPE",
    severity: "WARNING",
    lesson_id: 30,
    teacher_id: 6,
    class_id: 1,
    subject_id: 5,
    time_slot_id: 12,
    message: "",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: 9,
    identity_key: "ROOM_MISSING_FOR_TYPE:30",
    ...fields,
  };
}

describe("planAdjustmentRefresh", () => {
  const draft = { isAdmin: true, versionStatus: "DRAFT", isEditModeOn: true, isCheckShown: true };

  it("reloads the timetable and the unscheduled panel and re-runs a shown check", () => {
    expect(planAdjustmentRefresh(draft)).toEqual({ reloadTimetable: true, reloadUnscheduled: true, rerunCheck: true });
  });

  it("never starts a check nobody asked for", () => {
    expect(planAdjustmentRefresh({ ...draft, isCheckShown: false }).rerunCheck).toBe(false);
  });

  it("leaves the unscheduled panel alone outside edit mode (換教師 works without it)", () => {
    expect(planAdjustmentRefresh({ ...draft, isEditModeOn: false })).toEqual({
      reloadTimetable: true,
      reloadUnscheduled: false,
      rerunCheck: true,
    });
  });

  it("does nothing for a TEACHER or a version that isn't a DRAFT", () => {
    const nothing = { reloadTimetable: false, reloadUnscheduled: false, rerunCheck: false };
    expect(planAdjustmentRefresh({ ...draft, isAdmin: false })).toEqual(nothing);
    expect(planAdjustmentRefresh({ ...draft, versionStatus: "PUBLISHED" })).toEqual(nothing);
    expect(planAdjustmentRefresh({ ...draft, versionStatus: "ARCHIVED" })).toEqual(nothing);
    expect(planAdjustmentRefresh({ ...draft, versionStatus: null })).toEqual(nothing);
  });
});

describe("isLocatedProblemGone", () => {
  const located = violationIdentityKey(violation({}));

  it("is gone once the newer check no longer has the problem", () => {
    expect(isLocatedProblemGone(located, [])).toBe(true);
    expect(isLocatedProblemGone(located, [violation({ lesson_id: 31, identity_key: "ROOM_MISSING_FOR_TYPE:31" })])).toBe(true);
  });

  it("stays while the problem is still there, even described in another slot", () => {
    expect(isLocatedProblemGone(located, [violation({})])).toBe(false);
    expect(isLocatedProblemGone(located, [violation({ time_slot_id: 99 })])).toBe(false);
  });

  it("keeps the mark when nothing is known", () => {
    expect(isLocatedProblemGone(null, [])).toBe(false);
    expect(isLocatedProblemGone(located, null)).toBe(false);
  });
});
