import { describe, expect, it } from "vitest";
import { DELETE_WARNING, PUBLISHED_DELETE_HINT, canDeleteRecord } from "./versionDelete";

describe("canDeleteRecord", () => {
  it("allows every record but the published one", () => {
    expect(canDeleteRecord({ is_published: false })).toBe(true);
    expect(canDeleteRecord({ is_published: true })).toBe(false);
  });

  it("uses the backend's wording for the published hint", () => {
    expect(PUBLISHED_DELETE_HINT).toBe("已發布的排課紀錄無法刪除");
  });

  it("warns that the settings go too", () => {
    expect(DELETE_WARNING).toContain("排課設定與課表都會一併刪除");
  });
});
