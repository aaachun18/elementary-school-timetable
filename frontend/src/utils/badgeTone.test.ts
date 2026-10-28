import { describe, expect, it } from "vitest";
import { badgeClass, type BadgeTone } from "./badgeTone";
import { BADGE_DANGER, BADGE_INFO, BADGE_MANUAL, BADGE_NEUTRAL, BADGE_SUCCESS, BADGE_WARNING } from "../styles/ui";

describe("badgeClass", () => {
  it("maps every tone to its own badge classes", () => {
    const expected: Record<BadgeTone, string> = {
      info: BADGE_INFO,
      manual: BADGE_MANUAL,
      warning: BADGE_WARNING,
      success: BADGE_SUCCESS,
      neutral: BADGE_NEUTRAL,
      danger: BADGE_DANGER,
    };
    for (const [tone, classes] of Object.entries(expected)) {
      expect(badgeClass(tone as BadgeTone)).toBe(classes);
    }
    expect(new Set(Object.values(expected)).size).toBe(6);
  });

  it("uses the badge tokens, not raw Tailwind colors", () => {
    expect(badgeClass("info")).toContain("bg-badge-info-bg");
    expect(badgeClass("info")).toContain("text-badge-info-fg");
    expect(badgeClass("success")).toContain("text-badge-success-fg");
    // danger reuses the danger tokens (danger-hover on danger-soft >= 4.5,
    // styles/tokens.test.ts).
    expect(badgeClass("danger")).toContain("bg-danger-soft");
    expect(badgeClass("danger")).toContain("text-danger-hover");
  });
});
