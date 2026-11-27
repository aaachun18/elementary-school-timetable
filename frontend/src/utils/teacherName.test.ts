import { describe, expect, it } from "vitest";
import {
  formatTeacherName,
  sameNameAccounts,
  splitTeacherLabel,
  teacherDisplayName,
  usernamesByTeacherId,
} from "./teacherName";

const TEACHERS = [
  { id: 1, name: "王老師" },
  { id: 2, name: "李老師" },
  { id: 11, name: "王老師" },
];
const USERNAMES = new Map([
  [1, "teacher01"],
  [2, "teacher02"],
  [11, "teacher11"],
]);

describe("teacherDisplayName", () => {
  it("adds the account after a shared name, half-width parentheses, no space", () => {
    expect(teacherDisplayName(TEACHERS[0], TEACHERS, USERNAMES)).toBe("王老師(teacher01)");
    expect(teacherDisplayName(TEACHERS[2], TEACHERS, USERNAMES)).toBe("王老師(teacher11)");
  });

  it("leaves a name no one else has as it is", () => {
    expect(teacherDisplayName(TEACHERS[1], TEACHERS, USERNAMES)).toBe("李老師");
  });

  it("shows just the name when the account is not known", () => {
    expect(teacherDisplayName(TEACHERS[0], TEACHERS, new Map())).toBe("王老師");
  });
});

describe("sameNameAccounts", () => {
  it("lists only the shared-name teachers with a known account", () => {
    expect(sameNameAccounts(TEACHERS, USERNAMES)).toEqual(
      new Map([
        [1, "teacher01"],
        [11, "teacher11"],
      ]),
    );
    expect(sameNameAccounts(TEACHERS, new Map([[11, "teacher11"]]))).toEqual(new Map([[11, "teacher11"]]));
  });

  it("is empty with no teachers", () => {
    expect(sameNameAccounts([], USERNAMES).size).toBe(0);
  });
});

describe("formatTeacherName", () => {
  it("joins name and account, or returns the name", () => {
    expect(formatTeacherName("王老師", "teacher11")).toBe("王老師(teacher11)");
    expect(formatTeacherName("王老師", null)).toBe("王老師");
    expect(formatTeacherName("王老師", undefined)).toBe("王老師");
  });
});

describe("splitTeacherLabel", () => {
  const known = new Set(["teacher11"]);

  it("splits a known account off, keeping the 合併節 mark", () => {
    expect(splitTeacherLabel("王老師(teacher11)", known)).toEqual({ name: "王老師", account: "teacher11", mark: "" });
    expect(splitTeacherLabel("王老師(teacher11)*", known)).toEqual({ name: "王老師", account: "teacher11", mark: "*" });
  });

  it("never cuts a name whose parentheses are not a known account", () => {
    expect(splitTeacherLabel("王老師(代)", known)).toEqual({ name: "王老師(代)", account: null, mark: "" });
    expect(splitTeacherLabel("李老師*", known)).toEqual({ name: "李老師", account: null, mark: "*" });
  });
});

describe("usernamesByTeacherId", () => {
  it("maps teacher accounts and skips the others", () => {
    expect(
      usernamesByTeacherId([
        { teacher_id: 3, username: "teacher03" },
        { teacher_id: null, username: "coordinator" },
      ]),
    ).toEqual(new Map([[3, "teacher03"]]));
  });
});
