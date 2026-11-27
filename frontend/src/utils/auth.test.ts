import { describe, expect, it } from "vitest";
import { homePathFor } from "./auth";

describe("homePathFor", () => {
  it("sends the 系統管理員 to 學校管理 -- it has no scheduling pages", () => {
    expect(homePathFor("ADMIN")).toBe("/schools");
  });

  it("sends school accounts (and an unknown role) to 首頁", () => {
    expect(homePathFor("COORDINATOR")).toBe("/home");
    expect(homePathFor("TEACHER")).toBe("/home");
    expect(homePathFor(null)).toBe("/home");
  });
});
