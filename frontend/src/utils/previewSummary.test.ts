import { describe, expect, it } from "vitest";
import {
  PREVIEW_VISIBLE_CHANGES,
  PREVIEW_VISIBLE_LINES,
  buildPreviewSummary,
  describeMoveLine,
  describeReassignLine,
  describeSwapLine,
  previewLine,
  previewVerdict,
  shortSentence,
  visibleItems,
} from "./previewSummary";
import { diffViolations } from "./violationMerge";
import type { ConstraintViolationDetail } from "../types/scheduler";

function violation(fields: Partial<ConstraintViolationDetail>): ConstraintViolationDetail {
  return {
    type: "H1_TEACHER_CONFLICT",
    severity: "ERROR",
    lesson_id: null,
    teacher_id: null,
    class_id: null,
    subject_id: null,
    time_slot_id: null,
    message: "",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: null,
    ...fields,
  };
}

// The sentence is the message itself, so the tests need no name lookups.
function diff(before: ConstraintViolationDetail[], after: ConstraintViolationDetail[]) {
  return diffViolations(before, after, (v) => v.message);
}

function teacherClash(teacherId: number, slotId: number, lessonId: number): ConstraintViolationDetail {
  return violation({
    type: "H1_TEACHER_CONFLICT",
    teacher_id: teacherId,
    time_slot_id: slotId,
    lesson_id: lessonId,
    message: `王老師在星期二第 ${slotId} 節被同時排定兩堂課！`,
  });
}

const warning = violation({
  type: "TEACHER_MIN_WORKLOAD",
  severity: "WARNING",
  teacher_id: 9,
  identity_key: "TEACHER_MIN_WORKLOAD:9",
  message: "李老師的排課總節數低於每週最低授課節數！",
});

describe("previewVerdict", () => {
  it("is green without new problems, with the resolved count when there is one", () => {
    expect(previewVerdict(0, 0)).toEqual({ tone: "ok", text: "✓ 沒有新增問題" });
    expect(previewVerdict(0, 2)).toEqual({ tone: "ok", text: "✓ 沒有新增問題，解決 2 項" });
  });

  it("is red with the number of new problems", () => {
    expect(previewVerdict(1, 0)).toEqual({ tone: "problem", text: "會新增 1 項問題" });
    expect(previewVerdict(4, 1)).toEqual({ tone: "problem", text: "會新增 4 項問題，解決 1 項" });
  });
});

describe("buildPreviewSummary", () => {
  it("adds nothing: green verdict, no lines", () => {
    const summary = buildPreviewSummary(diff([], []));

    expect(summary.verdict.tone).toBe("ok");
    expect(summary.lines).toEqual([]);
    expect(summary.addsProblems).toBe(false);
    expect(summary.untouchedCount).toBe(0);
  });

  it("adds one problem: one short line with its category and suggestion kept for title/aria", () => {
    const summary = buildPreviewSummary(diff([], [teacherClash(1, 2, 10)]));

    expect(summary.verdict).toEqual({ tone: "problem", text: "會新增 1 項問題" });
    expect(summary.addsProblems).toBe(true);
    const [line] = summary.lines;
    expect(line.kind).toBe("error");
    expect(line.category).toBe("老師衝堂");
    expect(line.text).toBe("王老師在星期二第 2 節被同時排定兩堂課");
    expect(line.countLabel).toBeNull();
    expect(line.suggestion).not.toBeNull();
    expect(line.fullText).toBe(`老師衝堂：王老師在星期二第 2 節被同時排定兩堂課。建議：${line.suggestion}`);
  });

  it("merges one problem reported for two lessons into one line with （2 堂）", () => {
    const summary = buildPreviewSummary(diff([], [teacherClash(1, 2, 10), teacherClash(1, 2, 11)]));

    expect(summary.verdict.text).toBe("會新增 1 項問題");
    expect(summary.lines).toHaveLength(1);
    expect(summary.lines[0].countLabel).toBe("（2 堂）");
    expect(summary.lines[0].fullText).toContain("（2 堂）");
  });

  it("adds more than the visible lines: all listed, the rest behind 「另外 N 項」", () => {
    const after = [1, 2, 3, 4, 5].map((slot) => teacherClash(1, slot, 10 + slot));
    const summary = buildPreviewSummary(diff([], after));

    expect(summary.verdict.text).toBe("會新增 5 項問題");
    expect(summary.lines).toHaveLength(5);
    const collapsed = visibleItems(summary.lines, PREVIEW_VISIBLE_LINES, false);
    expect(collapsed.shown).toHaveLength(3);
    expect(collapsed.hiddenCount).toBe(2);
    expect(visibleItems(summary.lines, PREVIEW_VISIBLE_LINES, true)).toEqual({
      shown: summary.lines,
      hiddenCount: 0,
    });
  });

  it("resolves problems: counted in the verdict and listed last, without advice", () => {
    const clash = teacherClash(1, 2, 10);
    const added = teacherClash(1, 3, 12);
    const summary = buildPreviewSummary(diff([clash], [added]));

    expect(summary.verdict).toEqual({ tone: "problem", text: "會新增 1 項問題，解決 1 項" });
    expect(summary.lines.map((line) => line.kind)).toEqual(["error", "resolved"]);
    const resolved = summary.lines[1];
    expect(resolved.category).toBe("已解決");
    expect(resolved.suggestion).toBeNull();
    expect(resolved.fullText).toBe("已解決：王老師在星期二第 2 節被同時排定兩堂課");
  });

  it("adds only a warning: still green, the warning a light line at the end", () => {
    const summary = buildPreviewSummary(diff([], [warning, teacherClash(1, 2, 10)]));

    expect(summary.verdict.text).toBe("會新增 1 項問題");
    expect(summary.lines.map((line) => [line.kind, line.category])).toEqual([
      ["error", "老師衝堂"],
      ["warning", "警告"],
    ]);
    const onlyWarning = buildPreviewSummary(diff([], [warning]));
    expect(onlyWarning.verdict).toEqual({ tone: "ok", text: "✓ 沒有新增問題" });
    expect(onlyWarning.addsProblems).toBe(false);
    expect(onlyWarning.lines.map((line) => line.kind)).toEqual(["warning"]);
  });

  it("lists a problem that still exists but reads differently, and only counts the others", () => {
    const fixedBefore = violation({
      type: "FIXED_TIME_SLOT_MISMATCH",
      lesson_id: 7,
      message: "國語被固定在星期一第 1 節，但目前排在星期二第 3 節！",
    });
    const fixedAfter = { ...fixedBefore, message: "國語被固定在星期一第 1 節，但目前排在星期三第 4 節！" };
    const untouched = teacherClash(2, 6, 20);
    const summary = buildPreviewSummary(diff([fixedBefore, untouched], [fixedAfter, untouched]));

    expect(summary.verdict).toEqual({ tone: "ok", text: "✓ 沒有新增問題" });
    expect(summary.lines.map((line) => [line.kind, line.category])).toEqual([["unresolved", "仍未解決"]]);
    expect(summary.untouchedCount).toBe(1);
  });
});

describe("previewLine", () => {
  it("falls back to a generic category for an unknown type", () => {
    const line = previewLine({ sentence: "Something new.", type: "FUTURE", count: 1, violations: [] }, "error");

    expect(line.category).toBe("其他問題");
    expect(line.text).toBe("Something new");
    expect(line.suggestion).toBeNull();
  });
});

describe("shortSentence", () => {
  it("drops the closing punctuation only", () => {
    expect(shortSentence("王老師在星期二第 2 節被同時排定兩堂課！")).toBe("王老師在星期二第 2 節被同時排定兩堂課");
    expect(shortSentence("A、B！！")).toBe("A、B");
    expect(shortSentence("沒有標點")).toBe("沒有標點");
  });
});

describe("visibleItems", () => {
  it("shows everything up to the limit", () => {
    expect(visibleItems([1, 2, 3, 4], PREVIEW_VISIBLE_CHANGES, false)).toEqual({ shown: [1, 2, 3, 4], hiddenCount: 0 });
  });

  it("keeps the first rows of a long lesson block change", () => {
    expect(visibleItems([1, 2, 3, 4, 5, 6], PREVIEW_VISIBLE_CHANGES, false)).toEqual({
      shown: [1, 2, 3, 4],
      hiddenCount: 2,
    });
  });
});

describe("the 「這次會做什麼」 line", () => {
  it("moves one lesson, or a whole block", () => {
    expect(describeMoveLine("四年甲班 國語", "星期一第 2 節", "星期二第 2 節", 1)).toBe(
      "四年甲班 國語：星期一第 2 節 → 星期二第 2 節",
    );
    expect(describeMoveLine("四年甲班 自然", "星期一第 1 節", "星期三第 5 節", 2)).toBe(
      "四年甲班 自然：星期一第 1 節 → 星期三第 5 節（整組 2 節一起移動）",
    );
  });

  it("swaps two lessons, or two whole blocks", () => {
    expect(describeSwapLine("四年甲班 國語", "星期一第 2 節", "四年甲班 數學", "星期二第 2 節", 2)).toBe(
      "四年甲班 國語：星期一第 2 節 ↔ 四年甲班 數學：星期二第 2 節",
    );
    expect(describeSwapLine("四年甲班 自然", "星期一第 1 節", "四年甲班 數學", "星期二第 5 節", 4)).toBe(
      "四年甲班 自然：星期一第 1 節 ↔ 四年甲班 數學：星期二第 5 節（兩組連堂整組對調，共 4 節）",
    );
  });

  it("changes the teacher of a course", () => {
    expect(describeReassignLine("四年甲班 國語", "王老師", "李老師", 3)).toBe("四年甲班 國語：王老師 → 李老師（3 堂課）");
    expect(describeReassignLine("四年甲班 國語", null, "李老師", 0)).toBe(
      "四年甲班 國語：未指定教師 → 李老師（這個版本沒有要換的課，只更新指定教師）",
    );
  });
});
