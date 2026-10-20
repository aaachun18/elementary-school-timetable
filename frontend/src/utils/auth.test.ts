import { describe, expect, it } from "vitest";
import { homePathFor } from "./auth";

describe("homePathFor", () => {
  it("sends the 系統管理員 to 學校管理 -- it has no scheduling pages", () => {
    expect(homePathFor("ADMIN")).toBe("/schools");
  });

  it("sends school accounts (and an unknown role) to 首頁", () => {
    expect(homePathFor("COORDINATOR")).toBe("/");
    expect(homePathFor("TEACHER")).toBe("/");
    expect(homePathFor(null)).toBe("/");
  });
});
