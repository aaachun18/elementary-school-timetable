import { describe, expect, it } from "vitest";
import { canSeeCheckTags, checkTags, isCheckListOpen, type CheckTagInput } from "./checkTag";

function input(fields: Partial<CheckTagInput>): CheckTagInput {
  return { isChecking: false, hasFailed: false, hasResult: true, errorCount: 0, warningCount: 0, ...fields };
}

describe("checkTags", () => {
  it("is one green 無衝突 with a check mark with no error and no warning", () => {
    expect(checkTags(input({}))).toEqual({
      kind: "result",
      tags: [{ tone: "success", label: "無衝突", icon: "check" }],
    });
  });

  it("is one red tag with errors only", () => {
    expect(checkTags(input({ errorCount: 3 })).tags).toEqual([{ tone: "danger", label: "3 個錯誤", icon: "alert" }]);
  });

  it("is one amber tag with warnings only", () => {
    expect(checkTags(input({ warningCount: 2 })).tags).toEqual([{ tone: "warning", label: "2 個警告", icon: "alert" }]);
  });

  it("shows errors and warnings side by side, errors first", () => {
    expect(checkTags(input({ errorCount: 1, warningCount: 2 })).tags).toEqual([
      { tone: "danger", label: "1 個錯誤", icon: "alert" },
      { tone: "warning", label: "2 個警告", icon: "alert" },
    ]);
  });

  it("shows only 檢查中… while checking, whatever the last result was", () => {
    expect(checkTags(input({ isChecking: true, errorCount: 3 }))).toEqual({
      kind: "checking",
      tags: [{ tone: "neutral", label: "檢查中…", icon: null }],
    });
  });

  it("has no tag when the check failed or there is no result yet", () => {
    expect(checkTags(input({ hasFailed: true }))).toEqual({ kind: "failed", tags: [] });
    expect(checkTags(input({ hasResult: false }))).toEqual({ kind: "idle", tags: [] });
  });
});

describe("isCheckListOpen", () => {
  it("opens by itself only when there is an error or a warning", () => {
    expect(isCheckListOpen(input({}), null)).toBe(false);
    expect(isCheckListOpen(input({ errorCount: 1 }), null)).toBe(true);
    expect(isCheckListOpen(input({ warningCount: 1 }), null)).toBe(true);
  });

  it("follows a click either way", () => {
    expect(isCheckListOpen(input({}), true)).toBe(true);
    expect(isCheckListOpen(input({ errorCount: 1 }), false)).toBe(false);
  });

  it("stays closed without a result", () => {
    expect(isCheckListOpen(input({ hasResult: false }), true)).toBe(false);
  });
});

describe("canSeeCheckTags", () => {
  it("is only for the 教學組長 (the check API refuses a 一般老師)", () => {
    expect(canSeeCheckTags(true)).toBe(true);
    expect(canSeeCheckTags(false)).toBe(false);
  });
});
