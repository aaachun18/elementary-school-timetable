import { describe, expect, it } from "vitest";
import { formatSeconds } from "./seconds";

describe("formatSeconds", () => {
  it("keeps one decimal under 10 seconds", () => {
    expect(formatSeconds(2.43)).toBe("2.4");
    expect(formatSeconds(0)).toBe("0.0");
  });

  it("rounds to whole seconds from 10 seconds on", () => {
    expect(formatSeconds(10)).toBe("10");
    expect(formatSeconds(37.6)).toBe("38");
  });
});
