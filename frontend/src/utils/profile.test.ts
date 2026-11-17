import { describe, expect, it } from "vitest";
import type { Profile } from "../types/me";
import { getPasswordChangeError, hasEditableName, isUnassignedTeacher } from "./profile";

const TEACHER: Profile = {
  username: "t1@example.com",
  role: "TEACHER",
  school_id: 1,
  school_name: "示範國小",
  name: "王老師",
};

describe("isUnassignedTeacher", () => {
  it("is true only for an 一般老師 with no school", () => {
    expect(isUnassignedTeacher({ ...TEACHER, school_id: null, school_name: null })).toBe(true);
    expect(isUnassignedTeacher(TEACHER)).toBe(false);
    expect(isUnassignedTeacher({ ...TEACHER, role: "ADMIN", school_id: null })).toBe(false);
    expect(isUnassignedTeacher(null)).toBe(false);
  });
});

describe("hasEditableName", () => {
  it("lets 教學組長 / 一般老師 with a school edit their name", () => {
    expect(hasEditableName(TEACHER)).toBe(true);
    expect(hasEditableName({ ...TEACHER, role: "COORDINATOR" })).toBe(true);
  });

  it("gives the 系統管理員 and an unassigned teacher no name to edit", () => {
    expect(hasEditableName({ ...TEACHER, role: "ADMIN", school_id: null, name: null })).toBe(false);
    expect(hasEditableName({ ...TEACHER, school_id: null })).toBe(false);
  });
});

describe("getPasswordChangeError", () => {
  const draft = { currentPassword: "old-pass-1", newPassword: "new-pass-1", confirmPassword: "new-pass-1" };

  it("is null for a complete, matching draft", () => {
    expect(getPasswordChangeError(draft)).toBeNull();
  });

  it("names the first problem", () => {
    expect(getPasswordChangeError({ ...draft, currentPassword: "" })).toBe("請輸入目前密碼");
    expect(getPasswordChangeError({ ...draft, newPassword: "" })).toBe("請輸入新密碼");
    expect(getPasswordChangeError({ ...draft, newPassword: "short", confirmPassword: "short" })).toBe(
      "密碼至少需要 8 個字元",
    );
    expect(getPasswordChangeError({ ...draft, confirmPassword: "new-pass-2" })).toBe("兩次輸入的新密碼不一致");
  });
});
