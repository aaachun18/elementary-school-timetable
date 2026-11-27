import { describe, expect, it } from "vitest";
import { stepAccessibleLabel, stepStates } from "./stepper";

describe("stepStates", () => {
  it("marks the steps before the current one done and the rest to come", () => {
    expect(stepStates(4, 2)).toEqual(["done", "done", "current", "todo"]);
  });

  it("handles the first and the last step", () => {
    expect(stepStates(3, 0)).toEqual(["current", "todo", "todo"]);
    expect(stepStates(3, 2)).toEqual(["done", "done", "current"]);
  });

  it("has no current step when the index is outside the steps", () => {
    expect(stepStates(2, -1)).toEqual(["todo", "todo"]);
  });
});

describe("stepAccessibleLabel", () => {
  it("numbers the step from 1 and says its state", () => {
    expect(stepAccessibleLabel(1, "教師設定", "done")).toBe("第 2 步：教師設定（已完成）");
    expect(stepAccessibleLabel(0, "學年度與學期", "current")).toBe("第 1 步：學年度與學期（目前步驟）");
    expect(stepAccessibleLabel(5, "確認並排課", "todo")).toBe("第 6 步：確認並排課（尚未進行）");
  });
});
