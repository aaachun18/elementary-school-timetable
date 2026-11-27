import { describe, expect, it } from "vitest";
import {
  DEACTIVATE_FIRST_LINE,
  IMPACT_FAILED_TEXT,
  IMPACT_LOADING_TEXT,
  activeStatusBadge,
  classInUseText,
  deactivateDialogText,
  recordsInUse,
  visibleClasses,
  visibleItems,
  type DeactivationImpact,
} from "./deactivation";

function impact(fields: Partial<DeactivationImpact>): DeactivationImpact {
  return { published_records: 0, other_records: 0, not_scheduled_records: 0, grade_requirements: 0, ...fields };
}

describe("recordsInUse", () => {
  it("counts every 排課紀錄 whose timetable uses it, 已發布 included", () => {
    expect(recordsInUse(impact({ published_records: 1, other_records: 3, not_scheduled_records: 2 }))).toBe(4);
    expect(recordsInUse(impact({ not_scheduled_records: 2 }))).toBe(0);
  });
});

describe("deactivateDialogText", () => {
  it("is just the rule when nothing uses it", () => {
    for (const kind of ["class", "subject", "room"] as const) {
      const text = deactivateDialogText(kind, "音樂教室", { status: "ready", impact: impact({}) });
      expect(text.title).toBe("停用「音樂教室」？");
      expect(text.lines).toEqual(["停用後，新的排課不能再使用。"]);
      expect(text.confirmLabel).toBe("停用");
    }
  });

  it("adds how many 排課紀錄 use it, without splitting them", () => {
    const text = deactivateDialogText("room", "音樂教室", {
      status: "ready",
      impact: impact({ published_records: 1, other_records: 2, not_scheduled_records: 5 }),
    });
    expect(text.lines).toEqual([DEACTIVATE_FIRST_LINE, "已有 3 筆排課紀錄使用，需換成其他項目才能發布。"]);
  });

  it("never says a class must be replaced before publishing (not under H12)", () => {
    const text = deactivateDialogText("class", "一年甲班", { status: "ready", impact: impact({ published_records: 1 }) });
    expect(text.lines).toEqual([DEACTIVATE_FIRST_LINE]);
  });

  it("tells how many grade requirements a subject hides, only when there are some", () => {
    const text = deactivateDialogText("subject", "音樂", {
      status: "ready",
      impact: impact({ other_records: 2, grade_requirements: 6 }),
    });
    expect(text.lines).toEqual([
      DEACTIVATE_FIRST_LINE,
      "已有 2 筆排課紀錄使用，需換成其他項目才能發布。",
      "各年級需求 6 筆將隱藏，重新啟用後恢復。",
    ]);
    const unused = deactivateDialogText("subject", "音樂", { status: "ready", impact: impact({ grade_requirements: 6 }) });
    expect(unused.lines).toEqual([DEACTIVATE_FIRST_LINE, "各年級需求 6 筆將隱藏，重新啟用後恢復。"]);
  });

  it("never mentions grade requirements for anything but a subject", () => {
    const text = deactivateDialogText("room", "音樂教室", { status: "ready", impact: impact({ grade_requirements: 6 }) });
    expect(text.lines).toEqual([DEACTIVATE_FIRST_LINE]);
  });

  it("says an account can't log in any more", () => {
    const text = deactivateDialogText("account", "teacher01", { status: "ready", impact: impact({ other_records: 2 }) });
    expect(text.lines).toEqual([
      DEACTIVATE_FIRST_LINE,
      "已有 2 筆排課紀錄使用，需換成其他項目才能發布。",
      "對應的教師資料會一併停用，且該帳號無法再登入。",
    ]);
  });

  it("says when the counts are loading or failed", () => {
    expect(deactivateDialogText("subject", "音樂", { status: "loading" }).lines).toEqual([
      DEACTIVATE_FIRST_LINE,
      IMPACT_LOADING_TEXT,
    ]);
    expect(deactivateDialogText("subject", "音樂", { status: "failed" }).lines).toEqual([
      DEACTIVATE_FIRST_LINE,
      IMPACT_FAILED_TEXT,
    ]);
  });
});

describe("activeStatusBadge", () => {
  it("is a green 啟用中 or a gray 已停用", () => {
    expect(activeStatusBadge(true)).toEqual({ tone: "success", label: "啟用中" });
    expect(activeStatusBadge(false)).toEqual({ tone: "neutral", label: "已停用" });
  });
});

describe("visibleItems", () => {
  it("hides 已停用 items unless 「顯示已停用」 is on", () => {
    const items = [
      { id: 1, is_active: true },
      { id: 2, is_active: false },
    ];
    expect(visibleItems(items, false).map((item) => item.id)).toEqual([1]);
    expect(visibleItems(items, true).map((item) => item.id)).toEqual([1, 2]);
  });
});

describe("visibleClasses", () => {
  const classes = [
    { id: 1, grade_id: 1, is_active: true },
    { id: 2, grade_id: 1, is_active: false },
    { id: 3, grade_id: 2, is_active: true },
  ];

  it("hides 已停用 classes unless asked", () => {
    expect(visibleClasses(classes, null, false).map((item) => item.id)).toEqual([1, 3]);
    expect(visibleClasses(classes, null, true).map((item) => item.id)).toEqual([1, 2, 3]);
  });

  it("filters by grade too", () => {
    expect(visibleClasses(classes, 1, true).map((item) => item.id)).toEqual([1, 2]);
  });
});

describe("classInUseText", () => {
  it("says how many records use it and offers 停用", () => {
    expect(classInUseText("一年甲班", 3).message).toBe(
      "「一年甲班」已被 3 筆排課紀錄使用，無法刪除。可改為停用：停用後不會出現在新的排課中，舊紀錄仍保留。",
    );
  });
});
