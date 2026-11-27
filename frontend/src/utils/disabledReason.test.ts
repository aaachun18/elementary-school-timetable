import { describe, expect, it } from "vitest";
import { autoScheduleDisabledReason, saveTeachersDisabledReason } from "./disabledReason";

describe("autoScheduleDisabledReason", () => {
  const ready = { isRunning: false, isDone: false, teacherCount: 3, requirementCount: 12 };

  it("is null when 自動排課 can run", () => {
    expect(autoScheduleDisabledReason(ready)).toBeNull();
  });

  it("says no teacher has been set up", () => {
    expect(autoScheduleDisabledReason({ ...ready, teacherCount: 0 })).toBe("還沒設定參與教師");
  });

  it("says there is no requirement", () => {
    expect(autoScheduleDisabledReason({ ...ready, requirementCount: 0 })).toBe("還沒有任何科目需求");
  });

  it("names the missing teachers first when both are missing", () => {
    expect(autoScheduleDisabledReason({ ...ready, teacherCount: 0, requirementCount: 0 })).toBe("還沒設定參與教師");
  });

  it("says the record is already scheduled", () => {
    expect(autoScheduleDisabledReason({ ...ready, isDone: true })).toBe("這筆紀錄已經排好課了");
  });

  it("is null while running -- the label 「排課中…」 says it", () => {
    expect(autoScheduleDisabledReason({ ...ready, isRunning: true, teacherCount: 0 })).toBeNull();
  });
});

describe("saveTeachersDisabledReason", () => {
  const ready = { isSaving: false, checkedCount: 2, hasRangeError: false };

  it("is null when the teachers can be saved", () => {
    expect(saveTeachersDisabledReason(ready)).toBeNull();
  });

  it("asks to check at least one teacher", () => {
    expect(saveTeachersDisabledReason({ ...ready, checkedCount: 0 })).toBe("請先勾選至少一位老師");
  });

  it("asks to fix a weekly periods error", () => {
    expect(saveTeachersDisabledReason({ ...ready, hasRangeError: true })).toBe("請先修正每週節數的錯誤");
  });

  it("is null while saving -- the label 「儲存中…」 says it", () => {
    expect(saveTeachersDisabledReason({ ...ready, isSaving: true, checkedCount: 0 })).toBeNull();
  });
});
