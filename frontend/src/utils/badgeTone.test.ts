import { describe, expect, it } from "vitest";
import { badgeClass, type BadgeTone } from "./badgeTone";
import { BADGE_INFO, BADGE_MANUAL, BADGE_NEUTRAL, BADGE_SUCCESS, BADGE_WARNING } from "../styles/ui";

describe("badgeClass", () => {
  it("maps every tone to its own badge classes", () => {
    const expected: Record<BadgeTone, string> = {
      info: BADGE_INFO,
      manual: BADGE_MANUAL,
      warning: BADGE_WARNING,
      success: BADGE_SUCCESS,
      neutral: BADGE_NEUTRAL,
    };
    for (const [tone, classes] of Object.entries(expected)) {
      expect(badgeClass(tone as BadgeTone)).toBe(classes);
    }
    expect(new Set(Object.values(expected)).size).toBe(5);
  });

  it("uses the badge tokens, not raw Tailwind colors", () => {
    expect(badgeClass("info")).toContain("bg-badge-info-bg");
    expect(badgeClass("info")).toContain("text-badge-info-fg");
    expect(badgeClass("success")).toContain("text-badge-success-fg");
  });
});
