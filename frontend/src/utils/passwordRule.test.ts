import { describe, expect, it } from "vitest";
import { getPasswordRuleError, PASSWORD_MAX_BYTES, PASSWORD_MIN_LENGTH } from "./passwordRule";

const TOO_SHORT = "密碼至少需要 8 個字元";
const TOO_LONG = "密碼太長，請縮短（中文等非英數字元每字會佔用較多長度）";

describe("getPasswordRuleError", () => {
  it("uses the backend's limits", () => {
    expect(PASSWORD_MIN_LENGTH).toBe(8);
    expect(PASSWORD_MAX_BYTES).toBe(72);
  });

  it("refuses 7 characters and accepts 8", () => {
    expect(getPasswordRuleError("a".repeat(7))).toBe(TOO_SHORT);
    expect(getPasswordRuleError("a".repeat(8))).toBeNull();
  });

  it("accepts exactly 72 ASCII bytes and refuses 73", () => {
    expect(getPasswordRuleError("a".repeat(72))).toBeNull();
    expect(getPasswordRuleError("a".repeat(73))).toBe(TOO_LONG);
  });

  it("counts full-width characters as 3 UTF-8 bytes each", () => {
    // 24 × 3 = 72 bytes: allowed; 25 × 3 = 75 bytes: too long, although
    // only 25 characters.
    expect(getPasswordRuleError("密".repeat(24))).toBeNull();
    expect(getPasswordRuleError("密".repeat(25))).toBe(TOO_LONG);
  });

  it("counts characters, not UTF-16 units, for the minimum", () => {
    // 4 emoji = 4 characters (8 UTF-16 units): still too short.
    expect(getPasswordRuleError("😀😀😀😀")).toBe(TOO_SHORT);
    // 18 emoji = 18 characters, 72 bytes: allowed.
    expect(getPasswordRuleError("😀".repeat(18))).toBeNull();
  });

  it("checks the minimum first", () => {
    expect(getPasswordRuleError("")).toBe(TOO_SHORT);
  });
});
