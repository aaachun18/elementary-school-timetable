import { describe, expect, it } from "vitest";
import { recordsCardText, schoolDataCardText, wizardCardText } from "./homeCards";
import type { ScheduleVersion } from "../types/scheduleVersion";

function record(
  displayNumber: number | null,
  status: ScheduleVersion["status"],
  isPublished = false,
): Pick<ScheduleVersion, "display_number" | "status" | "is_published" | "copied_from_display_number"> {
  return { display_number: displayNumber, status, is_published: isPublished, copied_from_display_number: null };
}

describe("wizardCardText", () => {
  it("counts the records still 尚未排課", () => {
    expect(wizardCardText([record(1, "NOT_SCHEDULED"), record(2, "AUTO"), record(3, "NOT_SCHEDULED")])).toBe(
      "2 筆尚未排課的紀錄",
    );
  });

  it("says what the wizard does when nothing is waiting", () => {
    expect(wizardCardText([record(1, "AUTO")])).toBe("設定老師與科目需求，自動排出課表");
    expect(wizardCardText([])).toBe("設定老師與科目需求，自動排出課表");
  });
});

describe("recordsCardText", () => {
  it("counts the unpublished records and names the newest one's status", () => {
    expect(recordsCardText([record(2, "AUTO"), record(1, "MANUAL"), record(3, "AUTO", true)])).toBe(
      "2 筆未發布紀錄 · 最近一筆：手動排課",
    );
  });

  it("calls the published newest record 已發布", () => {
    expect(recordsCardText([record(1, "AUTO", true)])).toBe("0 筆未發布紀錄 · 最近一筆：已發布");
  });

  it("leaves out a working copy (no 編號) and handles no records", () => {
    expect(recordsCardText([record(null, "EDITING"), record(1, "AUTO")])).toBe("1 筆未發布紀錄 · 最近一筆：自動排課");
    expect(recordsCardText([record(null, "EDITING")])).toBe("還沒有排課紀錄");
  });
});

describe("schoolDataCardText", () => {
  it("joins the teacher and class counts", () => {
    expect(schoolDataCardText(10, 6)).toBe("10 位老師 · 6 個班級");
  });
});
