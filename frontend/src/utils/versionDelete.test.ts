import { describe, expect, it } from "vitest";
import { DELETE_WARNING, PUBLISHED_DELETE_HINT, canDeleteRecord } from "./versionDelete";

describe("canDeleteRecord", () => {
  it("allows every record but the published one", () => {
    expect(canDeleteRecord({ is_published: false })).toBe(true);
    expect(canDeleteRecord({ is_published: true })).toBe(false);
  });

  it("says why the published record's trash button is disabled", () => {
    expect(PUBLISHED_DELETE_HINT).toBe("已發布的紀錄不可刪除");
  });

  it("warns that the settings go too", () => {
    expect(DELETE_WARNING).toContain("排課設定與課表都會一併刪除");
  });
});
