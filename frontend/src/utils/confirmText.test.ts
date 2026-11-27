import { describe, expect, it } from "vitest";
import {
  CANCEL_LABEL,
  deleteButtonLabel,
  deleteConfirmText,
  deleteRecordConfirmText,
  type DeletableKind,
} from "./confirmText";

const KINDS: DeletableKind[] = ["class", "subject", "room", "gradeRequirement", "school", "account"];
const GENERIC_LABELS = ["確定", "取消", "確認"];

// Task 99: the negative option is always 「取消」; only the confirm button
// names the action.

describe("deleteConfirmText", () => {
  it("names the row in the title and the kind on the confirm button", () => {
    const text = deleteConfirmText("class", "一年甲班");
    expect(text.title).toBe("刪除「一年甲班」？");
    expect(text.confirmLabel).toBe("刪除班級");
    expect(text.cancelLabel).toBe(CANCEL_LABEL);
    expect(CANCEL_LABEL).toBe("取消");
    expect(text.tone).toBe("danger");
  });

  it.each(KINDS)("%s: says it can't be undone; confirm names the action, cancel is 取消", (kind) => {
    const text = deleteConfirmText(kind, "x");
    expect(text.message).toContain("刪除後無法復原");
    expect(text.tone).toBe("danger");
    for (const generic of GENERIC_LABELS) {
      expect(text.confirmLabel).not.toBe(generic);
    }
    expect(text.cancelLabel).toBe(CANCEL_LABEL);
  });

  it("tells what the backend refuses or removes along with it", () => {
    expect(deleteConfirmText("class", "x").message).toContain("系統會擋下刪除");
    expect(deleteConfirmText("room", "x").message).toContain("系統會擋下刪除");
    expect(deleteConfirmText("subject", "x").message).toContain("年級科目需求");
    expect(deleteConfirmText("school", "x").message).toContain("會一併刪除");
    expect(deleteConfirmText("gradeRequirement", "x").message).toContain("已經建立的排課紀錄不受影響");
    expect(deleteConfirmText("account", "x").message).toContain("停用");
  });

  it("an account too: 取消 / 刪除帳號", () => {
    expect(deleteConfirmText("account", "teacher01").cancelLabel).toBe(CANCEL_LABEL);
    expect(deleteConfirmText("account", "teacher01").confirmLabel).toBe("刪除帳號");
  });
});

describe("deleteButtonLabel", () => {
  it("says which row the trash button deletes", () => {
    expect(deleteButtonLabel("class", "一年甲班")).toBe("刪除班級「一年甲班」");
    expect(deleteButtonLabel("gradeRequirement", "一年級的國語")).toBe("刪除科目需求「一年級的國語」");
  });
});

describe("deleteRecordConfirmText", () => {
  it("names the number, carries the label (with its status) and warns", () => {
    const text = deleteRecordConfirmText(3, "編號 3・115 學年度第 1 學期（自動排課）");
    expect(text.title).toBe("刪除排課紀錄編號 3？");
    expect(text.message).toContain("編號 3・115 學年度第 1 學期（自動排課）");
    expect(text.message).toContain("刪除後無法復原");
    expect(text.confirmLabel).toBe("刪除紀錄");
    expect(text.cancelLabel).toBe(CANCEL_LABEL);
    expect(text.tone).toBe("danger");
  });

  it("falls back to a plain title without a number", () => {
    expect(deleteRecordConfirmText(null, "編輯中").title).toBe("刪除這筆排課紀錄？");
  });
});
