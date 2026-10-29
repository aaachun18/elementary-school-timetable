import { describe, expect, it } from "vitest";
import { IDLE_TIMEOUT_MS, REFRESH_INTERVAL_MS, sessionAction } from "./session";

const MINUTE = 60 * 1000;

describe("sessionAction", () => {
  it("logs out after 30 minutes without any activity", () => {
    expect(IDLE_TIMEOUT_MS).toBe(30 * MINUTE);
    expect(sessionAction({ now: 30 * MINUTE, lastActivityAt: 0, lastRefreshAt: 0 })).toBe("logout");
    expect(sessionAction({ now: 29 * MINUTE, lastActivityAt: 0, lastRefreshAt: 0 })).toBe("none");
  });

  // Regression: the token used to run out a fixed hour after logging in,
  // however busy the person was.
  it("never logs out someone who keeps working, however long", () => {
    let lastRefreshAt = 0;
    for (let now = MINUTE; now <= 3 * 60 * MINUTE; now += MINUTE) {
      const action = sessionAction({ now, lastActivityAt: now - 1000, lastRefreshAt });
      expect(action).not.toBe("logout");
      if (action === "refresh") {
        lastRefreshAt = now;
      }
    }
  });

  it("renews the token for someone active, at most every 5 minutes", () => {
    expect(REFRESH_INTERVAL_MS).toBe(5 * MINUTE);
    expect(sessionAction({ now: 5 * MINUTE, lastActivityAt: 4 * MINUTE, lastRefreshAt: 0 })).toBe("refresh");
    expect(sessionAction({ now: 4 * MINUTE, lastActivityAt: 3 * MINUTE, lastRefreshAt: 0 })).toBe("none");
  });

  it("doesn't renew the token of someone idle since it was issued", () => {
    expect(sessionAction({ now: 10 * MINUTE, lastActivityAt: 1 * MINUTE, lastRefreshAt: 2 * MINUTE })).toBe("none");
  });
});
